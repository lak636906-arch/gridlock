import math
import random
import time
import pygame
import sys

# --- CONFIGURATION & COLORS ---
BG_MAIN = (22, 21, 18)
BG_PANEL = (38, 36, 33)
BG_PANEL_HEADER = (30, 28, 26)
BG_ROW_ALT = (44, 42, 38)
BTN_BG = (54, 51, 47)
BTN_HOVER = (72, 68, 63)
ACCENT_GREEN = (129, 182, 76)
ACCENT_GREEN_HOVER = (145, 200, 88)
ACCENT_BLUE = (65, 145, 235)
ACCENT_BLUE_HOVER = (85, 165, 250)
ACCENT_GOLD = (245, 200, 70)
ACCENT_RED = (220, 60, 60)
ACCENT_PURPLE = (165, 110, 235)
TEXT_PRIMARY = (240, 240, 240)
TEXT_MUTED = (165, 162, 158)

LIGHT_SQUARE = (240, 217, 181)
DARK_SQUARE = (181, 136, 99)
HIGHLIGHT_SELECTED = (186, 202, 68)
HIGHLIGHT_LAST_MOVE = (246, 246, 105, 165)
HIGHLIGHT_PREMOVE = (225, 45, 45, 160)
HIGHLIGHT_CHECK = (230, 55, 55)

DARK_MOVE_DOT = (20, 20, 20, 95)
DARK_CAPTURE_TINT = (180, 30, 30, 110)
DARK_CAPTURE_RING = (30, 30, 30, 160)
PREMOVE_DOT = (220, 40, 40, 140)
PREMOVE_RING = (220, 40, 40, 200)

WHITE_FILL = (250, 250, 250)
WHITE_OUTLINE = (20, 20, 20)
BLACK_FILL = (35, 35, 35)
BLACK_OUTLINE = (235, 235, 235)

ROWS, COLS = 8, 8
PROMOTION_CAPTURES_REQUIRED = 5
MOVE_GLIDE_DURATION = 0.16

BOT_LEVELS = {
    1:  {"name": "Bluechair 1",  "elo": 100,  "desc": "Picks the worst possible moves"},
    2:  {"name": "Bluechair 2",  "elo": 250,  "desc": "Heavily favors losing material"},
    3:  {"name": "Bluechair 3",  "elo": 400,  "desc": "Frequently hangs pieces"},
    4:  {"name": "Bluechair 4",  "elo": 550,  "desc": "Mostly random with minor blunders"},
    5:  {"name": "Bluechair 5",  "elo": 700,  "desc": "Purely random legal moves"},
    6:  {"name": "Bluechair 6",  "elo": 900,  "desc": "Spots occasional free captures"},
    7:  {"name": "Bluechair 7",  "elo": 1100, "desc": "1-ply material evaluation with noise"},
    8:  {"name": "Bluechair 8",  "elo": 1300, "desc": "1-ply lookahead with center control"},
    9:  {"name": "Bluechair 9",  "elo": 1500, "desc": "2-ply search with occasional slips"},
    10: {"name": "Bluechair 10", "elo": 1700, "desc": "Clean 2-ply minimax search"},
    11: {"name": "Bluechair 11", "elo": 1950, "desc": "2-ply + capture quiescence"},
    12: {"name": "Bluechair 12", "elo": 2200, "desc": "3-ply alpha-beta search"},
    13: {"name": "Bluechair 13", "elo": 2500, "desc": "3-ply + deep tactical quiescence"},
    14: {"name": "Bluechair 14", "elo": 2850, "desc": "4-ply iterative alpha-beta search"},
    15: {"name": "Bluechair 15", "elo": 3500, "desc": "Unbeatable iterative deepening + TT"},
}


class Piece:
    def __init__(self, color, name):
        self.color = color
        self.name = name
        self.has_moved = False
        self.captures = 0


def create_empty_board():
    return [[None for _ in range(COLS)] for _ in range(ROWS)]


def create_board():
    board = create_empty_board()

    # --- BLACK PIECES (Top: Ranks 8 and 7) ---
    board[0][0] = Piece("Black", "Hook")     # a8
    board[0][1] = Piece("Black", "Hopper")      # b8
    board[0][2] = Piece("Black", "Diamond")  # c8
    board[0][3] = Piece("Black", "Master")   # d8
    board[0][4] = Piece("Black", "King")     # e8
    board[0][5] = Piece("Black", "Diamond")  # f8
    board[0][6] = Piece("Black", "Hopper")      # g8
    board[0][7] = Piece("Black", "Hook")     # h8
    for col in range(COLS):
        board[1][col] = Piece("Black", "Tacker")  # a7 - h7

    # --- WHITE PIECES (Bottom: Ranks 2 and 1) ---
    for col in range(COLS):
        board[6][col] = Piece("White", "Tacker")  # a2 - h2
    board[7][0] = Piece("White", "Hook")     # a1
    board[7][1] = Piece("White", "Hopper")      # b1
    board[7][2] = Piece("White", "Diamond")  # c1
    board[7][3] = Piece("White", "Master")   # d1
    board[7][4] = Piece("White", "King")     # e1
    board[7][5] = Piece("White", "Diamond")  # f1
    board[7][6] = Piece("White", "Hopper")      # g1
    board[7][7] = Piece("White", "Hook")     # h1

    return board


def clone_board(board):
    new_board = create_empty_board()
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if p is not None:
                copied = Piece(p.color, p.name)
                copied.has_moved = p.has_moved
                copied.captures = p.captures
                new_board[r][c] = copied
    return new_board


def sq_to_algebraic(sq):
    r, c = sq
    file_char = chr(ord('a') + c)
    rank_char = str(8 - r)
    return f"{file_char}{rank_char}"


def can_promote_to_master(piece):
    return piece.name not in ("Master", "King") and piece.captures >= PROMOTION_CAPTURES_REQUIRED


# --- PSEUDO-LEGAL MOVEMENT & CAPTURE LOGIC ---

def is_path_blocked(board, start, end):
    sr, sc = start
    er, ec = end
    row_step = 0 if sr == er else (1 if er > sr else -1)
    col_step = 0 if sc == ec else (1 if ec > sc else -1)

    curr_r = sr + row_step
    curr_c = sc + col_step
    while (curr_r, curr_c) != (er, ec):
        if board[curr_r][curr_c] is not None:
            return True
        curr_r += row_step
        curr_c += col_step

    return False


def is_directional_edge(er, ec, row_step, col_step):
    next_r = er + row_step
    next_c = ec + col_step
    return not (0 <= next_r < ROWS and 0 <= next_c < COLS)


def check_line_slide_or_jump(board, start, end, piece):
    sr, sc = start
    er, ec = end

    row_step = 0 if sr == er else (1 if er > sr else -1)
    col_step = 0 if sc == ec else (1 if ec > sc else -1)

    target = board[er][ec]
    if target is not None:
        if target.color == piece.color:
            return False, []
        if is_directional_edge(er, ec, row_step, col_step) and not is_path_blocked(board, start, end):
            return True, [(er, ec)]
        return False, []

    jump_r = er - row_step
    jump_c = ec - col_step

    curr_r = sr + row_step
    curr_c = sc + col_step
    while (curr_r, curr_c) != (er, ec):
        if (curr_r, curr_c) != (jump_r, jump_c):
            if board[curr_r][curr_c] is not None:
                return False, []
        curr_r += row_step
        curr_c += col_step

    if (jump_r, jump_c) == (sr, sc):
        return True, []

    jumped_piece = board[jump_r][jump_c]

    if jumped_piece is None:
        return True, []

    if jumped_piece.color != piece.color:
        return True, [(jump_r, jump_c)]

    return False, []


def check_hook_move(board, start, end, piece):
    sr, sc = start
    er, ec = end

    target = board[er][ec]
    if target is not None and target.color == piece.color:
        return False, []

    is_vertical_1 = (sc == ec and abs(er - sr) == 1)
    is_horizontal_1 = (sr == er and abs(ec - sc) == 1)
    is_diagonal = (abs(er - sr) == abs(ec - sc))

    if not (is_vertical_1 or is_horizontal_1 or is_diagonal):
        return False, []

    if is_path_blocked(board, start, end):
        return False, []

    if target is not None and target.color != piece.color:
        return True, [(er, ec)]

    return True, []


def check_tacker_move(board, start, end, piece):
    sr, sc = start
    er, ec = end

    if not piece.has_moved:
        direction = -1 if piece.color == "White" else 1
        row_diff = er - sr

        if sc == ec and row_diff in (direction, 2 * direction):
            target = board[er][ec]
            if target is not None:
                if target.color != piece.color and is_directional_edge(er, ec, direction, 0) and not is_path_blocked(board, start, end):
                    return True, [(er, ec)]
                return False, []

            step_r = sr + direction
            while step_r != er + direction:
                if board[step_r][sc] is not None:
                    return False, []
                step_r += direction
            return True, []

        return False, []

    if sr != er and sc != ec:
        return False, []

    return check_line_slide_or_jump(board, start, end, piece)


def check_diamond_move(board, start, end, piece):
    sr, sc = start
    er, ec = end

    if abs(er - sr) != abs(ec - sc):
        return False, []

    return check_line_slide_or_jump(board, start, end, piece)


def check_king_move(board, start, end, piece):
    sr, sc = start
    er, ec = end

    is_orthogonal = (sr == er or sc == ec)
    is_diagonal = (abs(er - sr) == abs(ec - sc))

    if not (is_orthogonal or is_diagonal):
        return False, []

    return check_line_slide_or_jump(board, start, end, piece)


def check_hop_move(board, start, end, piece):
    sr, sc = start
    er, ec = end

    if max(abs(er - sr), abs(ec - sc)) != 2:
        return False, []

    target = board[er][ec]
    if target is not None and target.color == piece.color:
        return False, []

    captured_positions = []

    ortho_dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for dr, dc in ortho_dirs:
        if (er - sr) * dr + (ec - sc) * dc >= 1:
            for step in (1, 2):
                ar, ac = sr + dr * step, sc + dc * step
                if 0 <= ar < 8 and 0 <= ac < 8:
                    occupant = board[ar][ac]
                    if occupant is not None and occupant.color != piece.color:
                        if (ar, ac) not in captured_positions:
                            captured_positions.append((ar, ac))

    diag_dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for dr, dc in diag_dirs:
        corner_3 = [
            (sr + dr,     sc + 2 * dc),
            (sr + 2 * dr, sc + 2 * dc),
            (sr + 2 * dr, sc + dc),
        ]
        if (er, ec) in corner_3:
            ar, ac = sr + dr, sc + dc
            if 0 <= ar < 8 and 0 <= ac < 8:
                occupant = board[ar][ac]
                if occupant is not None and occupant.color != piece.color:
                    if (ar, ac) not in captured_positions:
                        captured_positions.append((ar, ac))

        if (er, ec) == (sr + 2 * dr, sc + 2 * dc):
            if target is not None and target.color != piece.color:
                if (er, ec) not in captured_positions:
                    captured_positions.append((er, ec))

    step_r = 0 if er == sr else (1 if er > sr else -1)
    step_c = 0 if ec == sc else (1 if ec > sc else -1)
    if target is not None and target.color != piece.color and is_directional_edge(er, ec, step_r, step_c):
        if (er, ec) not in captured_positions:
            captured_positions.append((er, ec))

    if target is None or (er, ec) in captured_positions:
        return True, captured_positions

    return False, []


def check_master_move(board, start, end, piece):
    valid_king, caps_king = check_king_move(board, start, end, piece)
    valid_hop, caps_hop = check_hop_move(board, start, end, piece)

    if not (valid_king or valid_hop):
        return False, []

    combined_captures = list(caps_king)
    for pos in caps_hop:
        if pos not in combined_captures:
            combined_captures.append(pos)

    return True, combined_captures


def get_pseudo_legal_move(board, start, end, piece):
    if start == end:
        return False, []

    if piece.name == "Tacker":
        return check_tacker_move(board, start, end, piece)
    elif piece.name == "Diamond":
        return check_diamond_move(board, start, end, piece)
    elif piece.name == "Hop":
        return check_hop_move(board, start, end, piece)
    elif piece.name == "King":
        return check_king_move(board, start, end, piece)
    elif piece.name == "Master":
        return check_master_move(board, start, end, piece)
    elif piece.name == "Hook":
        return check_hook_move(board, start, end, piece)

    return False, []


# --- FAST MOVE GENERATION & CHECK DETECTION ---

def find_king(board, color):
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if p is not None and p.color == color and p.name == "King":
                return (r, c)
    return None


def find_piece_position(board, target_piece):
    if target_piece is None:
        return None
    for r in range(ROWS):
        for c in range(COLS):
            if board[r][c] is target_piece:
                return (r, c)
    return None


def get_candidate_targets(board, sr, sc, piece):
    targets = []
    name = piece.name

    if name == "Tacker":
        if not piece.has_moved:
            d = -1 if piece.color == "White" else 1
            for step in (1, 2):
                nr = sr + d * step
                if 0 <= nr < 8:
                    targets.append((nr, sc))
        else:
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                for s in range(1, 8):
                    nr, nc = sr + dr * s, sc + dc * s
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        targets.append((nr, nc))
                    else:
                        break

    elif name == "Diamond":
        for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            for s in range(1, 8):
                nr, nc = sr + dr * s, sc + dc * s
                if 0 <= nr < 8 and 0 <= nc < 8:
                    targets.append((nr, nc))
                else:
                    break

    elif name == "Hook":
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = sr + dr, sc + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                targets.append((nr, nc))
        for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            for s in range(1, 8):
                nr, nc = sr + dr * s, sc + dc * s
                if 0 <= nr < 8 and 0 <= nc < 8:
                    targets.append((nr, nc))
                    if board[nr][nc] is not None:
                        break
                else:
                    break

    elif name == "Hop":
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                if max(abs(dr), abs(dc)) == 2:
                    nr, nc = sr + dr, sc + dc
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        targets.append((nr, nc))

    elif name == "King":
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                for s in range(1, 8):
                    nr, nc = sr + dr * s, sc + dc * s
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        targets.append((nr, nc))
                    else:
                        break

    elif name == "Master":
        seen = set()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                for s in range(1, 8):
                    nr, nc = sr + dr * s, sc + dc * s
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        seen.add((nr, nc))
                    else:
                        break
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                if max(abs(dr), abs(dc)) == 2:
                    nr, nc = sr + dr, sc + dc
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        seen.add((nr, nc))
        targets = list(seen)

    return targets


def is_in_check(board, color):
    king_pos = find_king(board, color)
    if king_pos is None:
        return True

    enemy_color = "Black" if color == "White" else "White"
    for r in range(ROWS):
        for c in range(COLS):
            attacker = board[r][c]
            if attacker is not None and attacker.color == enemy_color:
                for er, ec in get_candidate_targets(board, r, c, attacker):
                    is_valid, captures = get_pseudo_legal_move(board, (r, c), (er, ec), attacker)
                    if is_valid and king_pos in captures:
                        return True
    return False


def make_move_inplace(board, start_sq, end_sq, caps):
    sr, sc = start_sq
    er, ec = end_sq
    piece = board[sr][sc]
    captured_records = [(cr, cc, board[cr][cc]) for cr, cc in caps]
    for cr, cc, _ in captured_records:
        board[cr][cc] = None
    board[er][ec] = piece
    board[sr][sc] = None

    prev_moved = piece.has_moved
    prev_name = piece.name
    prev_captures = piece.captures

    piece.has_moved = True
    piece.captures += len(caps)
    if can_promote_to_master(piece):
        piece.name = "Master"

    return (piece, prev_moved, prev_name, prev_captures, captured_records)


def unmake_move_inplace(board, start_sq, end_sq, undo_info):
    sr, sc = start_sq
    er, ec = end_sq
    piece, prev_moved, prev_name, prev_captures, captured_records = undo_info
    piece.name = prev_name
    piece.has_moved = prev_moved
    piece.captures = prev_captures
    board[sr][sc] = piece
    board[er][ec] = None
    for cr, cc, cap_p in captured_records:
        board[cr][cc] = cap_p


def get_legal_moves(board, start):
    sr, sc = start
    piece = board[sr][sc]
    if piece is None:
        return {}

    legal_moves = {}
    for er, ec in get_candidate_targets(board, sr, sc, piece):
        is_valid, captures = get_pseudo_legal_move(board, start, (er, ec), piece)
        if not is_valid:
            continue

        undo = make_move_inplace(board, start, (er, ec), captures)
        in_chk = is_in_check(board, piece.color)
        unmake_move_inplace(board, start, (er, ec), undo)

        if not in_chk:
            legal_moves[(er, ec)] = captures

    return legal_moves


def get_all_legal_moves_list(board, color):
    moves = []
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if p is not None and p.color == color:
                legal = get_legal_moves(board, (r, c))
                for end_sq, caps in legal.items():
                    moves.append(((r, c), end_sq, caps))
    return moves


def get_premove_candidates(board, start):
    sr, sc = start
    piece = board[sr][sc]
    if piece is None:
        return {}

    legal = get_legal_moves(board, start)
    if legal:
        return legal

    candidates = {}
    for er, ec in get_candidate_targets(board, sr, sc, piece):
        is_valid, captures = get_pseudo_legal_move(board, start, (er, ec), piece)
        if is_valid:
            candidates[(er, ec)] = captures
    return candidates


def build_projected_board(board, premove_queue):
    proj = [[board[r][c] for c in range(COLS)] for r in range(ROWS)]
    for (sr, sc), (er, ec) in premove_queue:
        piece = proj[sr][sc]
        if piece is None:
            break
        is_valid, captures = get_pseudo_legal_move(proj, (sr, sc), (er, ec), piece)
        if not is_valid:
            break
        for cap_r, cap_c in captures:
            proj[cap_r][cap_c] = None
        proj[er][ec] = piece
        proj[sr][sc] = None
    return proj


def has_any_legal_moves(board, color):
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if p is not None and p.color == color:
                if get_legal_moves(board, (r, c)):
                    return True
    return False


# --- 15-LEVEL BLUECHAIR AI ENGINE ---

PIECE_VALUES = {
    "King": 100000,
    "Master": 1350,
    "Hop": 620,
    "Hook": 540,
    "Diamond": 410,
    "Tacker": 240,
}

CENTER_PST = [
    [0,  4,  8, 10, 10,  8,  4, 0],
    [4, 10, 16, 20, 20, 16, 10, 4],
    [8, 16, 26, 32, 32, 26, 16, 8],
    [10, 20, 32, 40, 40, 32, 20, 10],
    [10, 20, 32, 40, 40, 32, 20, 10],
    [8, 16, 26, 32, 32, 26, 16, 8],
    [4, 10, 16, 20, 20, 16, 10, 4],
    [0,  4,  8, 10, 10,  8,  4, 0],
]


def board_hash(board, turn):
    rows_sig = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p is not None:
                rows_sig.append((r, c, p.color[0], p.name[0], p.has_moved, min(p.captures, PROMOTION_CAPTURES_REQUIRED)))
    return (turn, tuple(rows_sig))


def evaluate_board(board, perspective_color):
    score = 0
    my_mat = 0
    opp_mat = 0
    my_king = None
    opp_king = None

    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p is None:
                continue

            if p.name == "King":
                if p.color == perspective_color:
                    my_king = (r, c)
                else:
                    opp_king = (r, c)
                continue

            val = PIECE_VALUES.get(p.name, 100)
            pst = CENTER_PST[r][c]

            if p.name == "Tacker":
                val += (55 if p.has_moved else 0) + pst
            else:
                val += pst

            if p.name != "Master" and p.captures > 0:
                val += min(p.captures, PROMOTION_CAPTURES_REQUIRED) * 65

            if p.color == perspective_color:
                score += val
                my_mat += val
            else:
                score -= val
                opp_mat += val

    if my_king is not None and opp_king is not None:
        if my_mat > opp_mat + 300:
            opp_edge_dist = min(opp_king[0], 7 - opp_king[0]) + min(opp_king[1], 7 - opp_king[1])
            king_dist = abs(my_king[0] - opp_king[0]) + abs(my_king[1] - opp_king[1])
            score += (6 - opp_edge_dist) * 35 + (14 - king_dist) * 18
        elif opp_mat > my_mat + 300:
            my_edge_dist = min(my_king[0], 7 - my_king[0]) + min(my_king[1], 7 - my_king[1])
            king_dist = abs(my_king[0] - opp_king[0]) + abs(my_king[1] - opp_king[1])
            score -= (6 - my_edge_dist) * 35 + (14 - king_dist) * 18

    return score


def order_moves(board, moves):
    def move_priority(m):
        start_sq, end_sq, caps = m
        er, ec = end_sq
        pri = CENTER_PST[er][ec]
        mover = board[start_sq[0]][start_sq[1]]
        if caps:
            pri += 500
            for cr, cc in caps:
                victim = board[cr][cc]
                if victim is not None:
                    pri += PIECE_VALUES.get(victim.name, 100) * 10
            if mover is not None and mover.name not in ("Master", "King"):
                if mover.captures + len(caps) >= PROMOTION_CAPTURES_REQUIRED:
                    pri += 1500
        if mover is not None and mover.name == "Tacker" and not mover.has_moved:
            pri += 80
        return pri

    return sorted(moves, key=move_priority, reverse=True)


def quiescence_search(board, turn, alpha, beta, perspective_color, q_depth=0):
    stand_pat = evaluate_board(board, perspective_color)
    maximizing = (turn == perspective_color)

    if maximizing:
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
    else:
        if stand_pat <= alpha:
            return alpha
        if stand_pat < beta:
            beta = stand_pat

    if q_depth >= 3:
        return stand_pat

    all_moves = get_all_legal_moves_list(board, turn)
    if not all_moves:
        if is_in_check(board, turn):
            return -99999 if maximizing else 99999
        return 0

    capture_moves = [m for m in all_moves if m[2]]
    if not capture_moves:
        return stand_pat

    capture_moves = order_moves(board, capture_moves)
    next_turn = "Black" if turn == "White" else "White"

    if maximizing:
        best = stand_pat
        for start_sq, end_sq, caps in capture_moves:
            undo = make_move_inplace(board, start_sq, end_sq, caps)
            val = quiescence_search(board, next_turn, alpha, beta, perspective_color, q_depth + 1)
            unmake_move_inplace(board, start_sq, end_sq, undo)

            if val > best:
                best = val
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best
    else:
        best = stand_pat
        for start_sq, end_sq, caps in capture_moves:
            undo = make_move_inplace(board, start_sq, end_sq, caps)
            val = quiescence_search(board, next_turn, alpha, beta, perspective_color, q_depth + 1)
            unmake_move_inplace(board, start_sq, end_sq, undo)

            if val < best:
                best = val
            if best < beta:
                beta = best
            if alpha >= beta:
                break
        return best


def minimax_ab(board, turn, depth, alpha, beta, perspective_color, use_quiescence, tt, deadline):
    if deadline is not None and time.perf_counter() > deadline:
        return evaluate_board(board, perspective_color), None

    state_key = (depth, board_hash(board, turn))
    if state_key in tt:
        return tt[state_key]

    moves = get_all_legal_moves_list(board, turn)
    maximizing = (turn == perspective_color)

    if not moves:
        if is_in_check(board, turn):
            mate_score = (-90000 - depth * 500) if maximizing else (90000 + depth * 500)
            return mate_score, None
        return 0, None

    if depth <= 0:
        if use_quiescence:
            val = quiescence_search(board, turn, alpha, beta, perspective_color, 0)
        else:
            val = evaluate_board(board, perspective_color)
        return val, None

    ordered = order_moves(board, moves)
    next_turn = "Black" if turn == "White" else "White"
    best_move = ordered[0]

    if maximizing:
        best_val = -float("inf")
        for start_sq, end_sq, caps in ordered:
            undo = make_move_inplace(board, start_sq, end_sq, caps)
            val, _ = minimax_ab(board, next_turn, depth - 1, alpha, beta, perspective_color, use_quiescence, tt, deadline)
            unmake_move_inplace(board, start_sq, end_sq, undo)

            if val > best_val:
                best_val = val
                best_move = (start_sq, end_sq, caps)
            if best_val > alpha:
                alpha = best_val
            if alpha >= beta:
                break
        tt[state_key] = (best_val, best_move)
        return best_val, best_move
    else:
        best_val = float("inf")
        for start_sq, end_sq, caps in ordered:
            undo = make_move_inplace(board, start_sq, end_sq, caps)
            val, _ = minimax_ab(board, next_turn, depth - 1, alpha, beta, perspective_color, use_quiescence, tt, deadline)
            unmake_move_inplace(board, start_sq, end_sq, undo)

            if val < best_val:
                best_val = val
                best_move = (start_sq, end_sq, caps)
            if best_val < beta:
                beta = best_val
            if alpha >= beta:
                break
        tt[state_key] = (best_val, best_move)
        return best_val, best_move


def score_all_root_moves(board, color, depth, use_quiescence, time_budget=None):
    moves = order_moves(board, get_all_legal_moves_list(board, color))
    if not moves:
        return []
    if len(moves) == 1:
        return [(0, moves[0])]

    tt = {}
    deadline = (time.perf_counter() + time_budget) if time_budget is not None else None
    next_turn = "Black" if color == "White" else "White"
    scored = []

    for start_sq, end_sq, caps in moves:
        undo = make_move_inplace(board, start_sq, end_sq, caps)
        val, _ = minimax_ab(
            board, next_turn, depth - 1,
            -float("inf"), float("inf"),
            color, use_quiescence, tt, deadline
        )
        unmake_move_inplace(board, start_sq, end_sq, undo)
        scored.append((val, (start_sq, end_sq, caps)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def pick_bot_move(board, color, level):
    moves = get_all_legal_moves_list(board, color)
    if not moves:
        return None
    if len(moves) == 1:
        return moves[0]

    if level == 1:
        scored = score_all_root_moves(board, color, depth=2, use_quiescence=True, time_budget=0.35)
        worst_score = scored[-1][0]
        worst_moves = [m for sc, m in scored if sc <= worst_score + 10]
        return random.choice(worst_moves)

    if level == 2:
        scored = score_all_root_moves(board, color, depth=2, use_quiescence=False, time_budget=0.25)
        cutoff = max(1, len(scored) // 6)
        return random.choice([m for _, m in scored[-cutoff:]])

    if level == 3:
        scored = score_all_root_moves(board, color, depth=1, use_quiescence=False)
        cutoff = max(1, int(len(scored) * 0.35))
        return random.choice([m for _, m in scored[-cutoff:]])

    if level == 4:
        if random.random() < 0.60:
            return random.choice(moves)
        scored = score_all_root_moves(board, color, depth=1, use_quiescence=False)
        return random.choice([m for _, m in scored[len(scored) // 2:]])

    if level == 5:
        return random.choice(moves)

    if level == 6:
        if random.random() < 0.50:
            return random.choice(moves)
        scored = score_all_root_moves(board, color, depth=1, use_quiescence=False)
        top_k = max(1, len(scored) // 2)
        return random.choice([m for _, m in scored[:top_k]])

    if level == 7:
        scored = score_all_root_moves(board, color, depth=1, use_quiescence=False)
        noisy = [(sc + random.gauss(0, 140), m) for sc, m in scored]
        noisy.sort(key=lambda x: x[0], reverse=True)
        return noisy[0][1]

    if level == 8:
        scored = score_all_root_moves(board, color, depth=1, use_quiescence=False)
        best_sc = scored[0][0]
        return random.choice([m for sc, m in scored if sc >= best_sc - 25])

    if level == 9:
        scored = score_all_root_moves(board, color, depth=2, use_quiescence=False, time_budget=0.25)
        noisy = [(sc + random.gauss(0, 75), m) for sc, m in scored]
        noisy.sort(key=lambda x: x[0], reverse=True)
        return noisy[0][1]

    if level == 10:
        scored = score_all_root_moves(board, color, depth=2, use_quiescence=False, time_budget=0.35)
        best_sc = scored[0][0]
        return random.choice([m for sc, m in scored if sc >= best_sc - 12])

    if level == 11:
        scored = score_all_root_moves(board, color, depth=2, use_quiescence=True, time_budget=0.45)
        best_sc = scored[0][0]
        return random.choice([m for sc, m in scored if sc >= best_sc - 8])

    if level == 12:
        scored = score_all_root_moves(board, color, depth=3, use_quiescence=False, time_budget=0.55)
        best_sc = scored[0][0]
        return random.choice([m for sc, m in scored if sc >= best_sc - 5])

    if level == 13:
        scored = score_all_root_moves(board, color, depth=3, use_quiescence=True, time_budget=0.70)
        return scored[0][1]

    if level == 14:
        deadline = time.perf_counter() + 0.85
        best_move = order_moves(board, moves)[0]
        tt = {}
        for d in range(1, 5):
            if time.perf_counter() > deadline:
                break
            _, mv = minimax_ab(board, color, d, -float("inf"), float("inf"), color, True, tt, deadline)
            if mv is not None:
                best_move = mv
        return best_move

    deadline = time.perf_counter() + 1.35
    best_move = order_moves(board, moves)[0]
    tt = {}
    for d in range(1, 7):
        if time.perf_counter() > deadline:
            break
        val, mv = minimax_ab(board, color, d, -float("inf"), float("inf"), color, True, tt, deadline)
        if mv is not None:
            best_move = mv
        if val >= 85000:
            break
    return best_move


# --- PYGAME RENDERING ---

def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def draw_piece_at_pixel(screen, cx, cy, piece, sq_size, badge_font=None):
    scale = 2
    surf_size = sq_size * scale
    surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)

    scx = surf_size // 2
    scy = surf_size // 2
    fill = WHITE_FILL if piece.color == "White" else BLACK_FILL
    outline = WHITE_OUTLINE if piece.color == "White" else BLACK_OUTLINE
    border_w = max(2, int(surf_size * 0.036))

    if piece.name == "Tacker":
        radius = int(surf_size * 0.32)
        pygame.draw.circle(surf, fill, (scx, scy), radius)
        pygame.draw.circle(surf, outline, (scx, scy), radius, width=border_w)

    elif piece.name == "Diamond":
        r = int(surf_size * 0.35)
        points = [
            (scx, scy - r),
            (scx + r, scy),
            (scx, scy + r),
            (scx - r, scy),
        ]
        pygame.draw.polygon(surf, fill, points)
        pygame.draw.polygon(surf, outline, points, width=border_w)

    elif piece.name == "Hook":
        total_w = int(surf_size * 0.64)
        total_h = int(surf_size * 0.70)
        top_y = scy - total_h // 2
        bot_y = top_y + total_h

        bar_h = int(surf_size * 0.12)
        band_t = int(surf_size * 0.125)

        base_left = scx - total_w // 2
        base_top = bot_y - bar_h
        base_rect = pygame.Rect(base_left, base_top, total_w, bar_h)

        arc_cx = scx + int(total_w * 0.03)
        arc_cy = top_y + int(total_h * 0.28)
        rx_out = int(total_w * 0.43)
        ry_out = int(total_h * 0.27)
        rx_in = rx_out - band_t
        ry_in = ry_out - band_t

        join_ang_out = math.radians(-122)
        join_ang_in = math.radians(-112)

        stem_left = arc_cx + math.cos(join_ang_out) * rx_out
        stem_join_y_out = arc_cy - math.sin(join_ang_out) * ry_out

        stem_right = stem_left + band_t
        stem_join_y_in = arc_cy - math.sin(join_ang_in) * ry_in

        steps = 36
        silhouette = [
            (stem_left, base_top),
            (stem_left, stem_join_y_out),
        ]

        for i in range(1, steps + 1):
            t = i / steps
            ang = math.radians(-122 + (190 - (-122)) * t)
            px = arc_cx + math.cos(ang) * rx_out
            py = arc_cy - math.sin(ang) * ry_out
            silhouette.append((px, py))

        tip_in_x = arc_cx + math.cos(math.radians(186)) * rx_in
        tip_in_y = arc_cy - math.sin(math.radians(186)) * ry_in
        silhouette.append((tip_in_x, tip_in_y))

        for i in range(1, steps + 1):
            t = i / steps
            ang = math.radians(186 + (-112 - 186) * t)
            px = arc_cx + math.cos(ang) * rx_in
            py = arc_cy - math.sin(ang) * ry_in
            silhouette.append((px, py))

        silhouette.append((stem_right, stem_join_y_in))
        silhouette.append((stem_right, base_top))

        pygame.draw.polygon(surf, fill, silhouette)
        pygame.draw.polygon(surf, outline, silhouette, width=border_w)
        pygame.draw.rect(surf, fill, base_rect)
        pygame.draw.rect(surf, outline, base_rect, width=border_w)

    elif piece.name == "Hop":
        total_w = int(surf_size * 0.62)
        total_h = int(surf_size * 0.66)
        base_h = int(total_h * 0.22)
        overhang = int(total_w * 0.16)
        pillar_w = int(total_w * 0.24)

        top_y = scy - total_h // 2
        bot_y = top_y + total_h
        base_top_y = bot_y - base_h

        base_left_x = scx - total_w // 2
        base_right_x = base_left_x + total_w

        left_pillar_outer_x = base_left_x + overhang
        left_pillar_inner_x = left_pillar_outer_x + pillar_w

        right_pillar_outer_x = base_right_x - overhang
        right_pillar_inner_x = right_pillar_outer_x - pillar_w

        points = [
            (left_pillar_outer_x, top_y),
            (left_pillar_inner_x, top_y),
            (left_pillar_inner_x, base_top_y),
            (right_pillar_inner_x, base_top_y),
            (right_pillar_inner_x, top_y),
            (right_pillar_outer_x, top_y),
            (right_pillar_outer_x, base_top_y),
            (base_right_x, base_top_y),
            (base_right_x, bot_y),
            (base_left_x, bot_y),
            (base_left_x, base_top_y),
            (left_pillar_outer_x, base_top_y),
        ]
        pygame.draw.polygon(surf, fill, points)
        pygame.draw.polygon(surf, outline, points, width=border_w)

    elif piece.name == "Master":
        total_w = int(surf_size * 0.66)
        total_h = int(surf_size * 0.68)
        bar_h = int(total_h * 0.19)
        overhang = int(total_w * 0.11)
        pillar_w = int(total_w * 0.15)

        top_y = scy - total_h // 2
        bot_y = top_y + total_h
        top_inner_y = top_y + bar_h
        bot_inner_y = bot_y - bar_h

        left_x = scx - total_w // 2
        right_x = left_x + total_w

        p_left_outer = left_x + overhang
        p_right_outer = right_x - overhang

        p_mid_left = scx - pillar_w // 2
        p_mid_right = p_mid_left + pillar_w

        p_left_inner = p_left_outer + pillar_w
        p_right_inner = p_right_outer - pillar_w

        outer_points = [
            (left_x, top_y),
            (right_x, top_y),
            (right_x, top_inner_y),
            (p_right_outer, top_inner_y),
            (p_right_outer, bot_inner_y),
            (right_x, bot_inner_y),
            (right_x, bot_y),
            (left_x, bot_y),
            (left_x, bot_inner_y),
            (p_left_outer, bot_inner_y),
            (p_left_outer, top_inner_y),
            (left_x, top_inner_y),
        ]
        pygame.draw.polygon(surf, fill, outer_points)
        pygame.draw.polygon(surf, outline, outer_points, width=border_w)

        left_window = pygame.Rect(p_left_inner, top_inner_y, p_mid_left - p_left_inner, bot_inner_y - top_inner_y)
        right_window = pygame.Rect(p_mid_right, top_inner_y, p_right_inner - p_mid_right, bot_inner_y - top_inner_y)

        for win in (left_window, right_window):
            surf.fill((0, 0, 0, 0), win)
            pygame.draw.rect(surf, outline, win, width=border_w)

    elif piece.name == "King":
        w = int(surf_size * 0.64)
        h = int(surf_size * 0.60)
        left_x = scx - w // 2
        right_x = left_x + w
        top_y = scy - h // 2
        bot_y = top_y + h

        points = [
            (left_x, bot_y),
            (left_x, top_y + int(h * 0.25)),
            (left_x + int(w * 0.28), top_y + int(h * 0.60)),
            (scx, top_y),
            (left_x + int(w * 0.72), top_y + int(h * 0.60)),
            (right_x, top_y + int(h * 0.25)),
            (right_x, bot_y),
        ]
        pygame.draw.polygon(surf, fill, points)
        pygame.draw.polygon(surf, outline, points, width=border_w)

    smooth_surf = pygame.transform.smoothscale(surf, (sq_size, sq_size))
    top_left_x = cx - sq_size // 2
    top_left_y = cy - sq_size // 2
    screen.blit(smooth_surf, (top_left_x, top_left_y))

    if badge_font is not None and piece.name not in ("Master", "King") and piece.captures > 0:
        badge_r = max(10, sq_size // 7)
        bx = top_left_x + sq_size - badge_r - 3
        by = top_left_y + badge_r + 3
        pygame.draw.circle(screen, (28, 26, 23), (bx, by), badge_r)
        pygame.draw.circle(screen, ACCENT_GOLD, (bx, by), badge_r, width=2)
        cnt_surf = badge_font.render(str(piece.captures), True, ACCENT_GOLD)
        screen.blit(cnt_surf, cnt_surf.get_rect(center=(bx, by)))


def draw_button(screen, rect, label, font, mouse_pos, bg=BTN_BG, hover=BTN_HOVER, text_col=TEXT_PRIMARY):
    is_hovered = rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, hover if is_hovered else bg, rect, border_radius=8)
    txt_surf = font.render(label, True, text_col)
    screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))


def draw_menu_icon(screen, icon_type, cx, cy, size, color):
    r = size // 2
    if icon_type == "bots":
        head = pygame.Rect(cx - r, cy - int(r * 0.75), size, int(size * 0.78))
        pygame.draw.rect(screen, color, head, width=2, border_radius=5)
        pygame.draw.line(screen, color, (cx, head.top), (cx, head.top - 7), 2)
        pygame.draw.circle(screen, color, (cx, head.top - 9), 3)
        pygame.draw.circle(screen, color, (cx - int(r * 0.42), cy - 2), 3)
        pygame.draw.circle(screen, color, (cx + int(r * 0.42), cy - 2), 3)
        pygame.draw.line(screen, color, (cx - int(r * 0.45), cy + int(r * 0.35)), (cx + int(r * 0.45), cy + int(r * 0.35)), 2)

    elif icon_type == "online":
        pygame.draw.circle(screen, color, (cx, cy), r, width=2)
        pygame.draw.ellipse(screen, color, (cx - r // 2, cy - r, r, size), width=2)
        pygame.draw.line(screen, color, (cx - r, cy), (cx + r, cy), 2)

    elif icon_type == "person":
        phone = pygame.Rect(cx - int(r * 0.65), cy - r, int(size * 0.65), size)
        pygame.draw.rect(screen, color, phone, width=2, border_radius=4)
        pygame.draw.circle(screen, color, (cx, phone.bottom - 5), 2)

    elif icon_type == "analysis":
        lens_r = int(r * 0.72)
        lcx, lcy = cx - 3, cy - 3
        pygame.draw.circle(screen, color, (lcx, lcy), lens_r, width=2)
        pygame.draw.line(screen, color, (lcx + int(lens_r * 0.7), lcy + int(lens_r * 0.7)), (cx + r, cy + r), 3)

    elif icon_type == "setup":
        grid = pygame.Rect(cx - r, cy - r, size, size)
        pygame.draw.rect(screen, color, grid, width=2, border_radius=4)
        pygame.draw.line(screen, color, (cx, grid.top), (cx, grid.bottom), 2)
        pygame.draw.line(screen, color, (grid.left, cy), (grid.right, cy), 2)


def draw_board_preview(screen, board, board_x, board_y, board_size, sq_size):
    board_border = pygame.Rect(board_x - 3, board_y - 3, board_size + 6, board_size + 6)
    pygame.draw.rect(screen, (55, 52, 48), board_border, border_radius=4)

    for r in range(ROWS):
        for c in range(COLS):
            is_light = (r + c) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            sq_rect = pygame.Rect(board_x + c * sq_size, board_y + r * sq_size, sq_size, sq_size)
            pygame.draw.rect(screen, color, sq_rect)

    for r in range(ROWS):
        for c in range(COLS):
            piece = board[r][c]
            if piece is not None:
                cx = board_x + c * sq_size + sq_size // 2
                cy = board_y + r * sq_size + sq_size // 2
                draw_piece_at_pixel(screen, cx, cy, piece, sq_size)


def draw_main_menu(
    screen, win_w, win_h, board, board_x, board_y, board_size, sq_size,
    mouse_pos, fonts, emoji_font, menu_buttons, btn_exit, menu_notice
):
    font_hero, font_title, font_bold, font_med, font_small, _ = fonts
    screen.fill(BG_MAIN)

    preview_board_x = win_w - board_size - max(48, (win_w // 2 - board_size) // 2)
    if preview_board_x < win_w // 2:
        preview_board_x = win_w // 2 + 20
    draw_board_preview(screen, board, preview_board_x, board_y, board_size, sq_size)

    left_area_w = preview_board_x
    left_center_x = left_area_w // 2

    btn_w = min(380, left_area_w - 60)
    btn_h = 62
    btn_gap = 14
    total_block_h = 68 + 5 * btn_h + 4 * btn_gap
    start_y = (win_h - total_block_h) // 2

    play_surf = font_hero.render("Play", True, TEXT_PRIMARY)
    screen.blit(play_surf, play_surf.get_rect(center=(left_center_x, start_y + 22)))

    modes = [
        ("bots",     "\U0001F916", "Bots",           "Challenge Bluechair (Levels 1 - 15)"),
        ("online",   "\U0001F310", "Online",         "Play over the internet"),
        ("person",   "\U0001F4F1", "Play in Person", "Pass & play on this device"),
        ("analysis", "\U0001F50D", "Analysis",       "Explore moves freely"),
        ("setup",    "\U0001F6E0", "Setup Position", "Build custom boards & test puzzles"),
    ]

    for idx, (key, emoji_char, title, subtitle) in enumerate(modes):
        by = start_y + 68 + idx * (btn_h + btn_gap)
        bx = left_center_x - btn_w // 2
        rect = menu_buttons[key]
        rect.update(bx, by, btn_w, btn_h)

        is_hovered = rect.collidepoint(mouse_pos)
        if key == "bots":
            bg_col = ACCENT_GREEN_HOVER if is_hovered else ACCENT_GREEN
            title_col = (20, 20, 20)
            sub_col = (35, 45, 25)
            icon_col = (20, 20, 20)
        else:
            bg_col = BTN_HOVER if is_hovered else BG_PANEL
            title_col = TEXT_PRIMARY
            sub_col = TEXT_MUTED
            icon_col = ACCENT_GREEN if is_hovered else TEXT_PRIMARY

        pygame.draw.rect(screen, bg_col, rect, border_radius=12)
        if key != "bots":
            pygame.draw.rect(screen, (62, 59, 54), rect, width=1, border_radius=12)

        icon_cx = rect.x + 36
        icon_cy = rect.centery
        if emoji_font is not None:
            em_surf = emoji_font.render(emoji_char, True, title_col)
            if em_surf.get_width() > 8:
                screen.blit(em_surf, em_surf.get_rect(center=(icon_cx, icon_cy)))
            else:
                draw_menu_icon(screen, key, icon_cx, icon_cy, 24, icon_col)
        else:
            draw_menu_icon(screen, key, icon_cx, icon_cy, 24, icon_col)

        t_surf = font_bold.render(title, True, title_col)
        s_surf = font_small.render(subtitle, True, sub_col)
        screen.blit(t_surf, (rect.x + 70, rect.y + 10))
        screen.blit(s_surf, (rect.x + 70, rect.y + 36))

    if menu_notice:
        notice_y = start_y + total_block_h + 18
        n_surf = font_small.render(menu_notice, True, ACCENT_GOLD)
        screen.blit(n_surf, n_surf.get_rect(center=(left_center_x, notice_y)))

    btn_exit.update(24, 24, 150, 38)
    draw_button(screen, btn_exit, "Exit (Esc)", font_small, mouse_pos)


def draw_bot_select_menu(
    screen, win_w, win_h, board, board_y, board_size, sq_size,
    mouse_pos, fonts, selected_bot_level, level_rects, btn_start_bot, btn_back_menu, btn_exit
):
    font_hero, font_title, font_bold, font_med, font_small, _ = fonts
    screen.fill(BG_MAIN)

    preview_board_x = win_w - board_size - max(48, (win_w // 2 - board_size) // 2)
    if preview_board_x < win_w // 2:
        preview_board_x = win_w // 2 + 20
    draw_board_preview(screen, board, preview_board_x, board_y, board_size, sq_size)

    left_area_w = preview_board_x
    left_center_x = left_area_w // 2

    panel_w = min(480, left_area_w - 48)
    panel_x = left_center_x - panel_w // 2

    title_surf = font_title.render("Choose Bluechair Bot (1 - 15)", True, TEXT_PRIMARY)
    screen.blit(title_surf, title_surf.get_rect(center=(left_center_x, board_y + 18)))

    cols = 3
    rows = 5
    gap_x = 10
    gap_y = 10
    card_w = (panel_w - (cols - 1) * gap_x) // cols
    card_h = 56
    grid_top = board_y + 52

    for lvl in range(1, 16):
        idx = lvl - 1
        r = idx // cols
        c = idx % cols
        cx = panel_x + c * (card_w + gap_x)
        cy = grid_top + r * (card_h + gap_y)
        rect = level_rects[lvl]
        rect.update(cx, cy, card_w, card_h)

        is_sel = (lvl == selected_bot_level)
        is_hov = rect.collidepoint(mouse_pos)

        if is_sel:
            bg = ACCENT_PURPLE if lvl == 15 else (ACCENT_RED if lvl == 1 else ACCENT_BLUE)
            fg = (255, 255, 255)
            sub_fg = (230, 240, 255)
        else:
            bg = BTN_HOVER if is_hov else BG_PANEL
            fg = TEXT_PRIMARY
            sub_fg = TEXT_MUTED

        pygame.draw.rect(screen, bg, rect, border_radius=9)
        if not is_sel:
            pygame.draw.rect(screen, (62, 59, 54), rect, width=1, border_radius=9)

        info = BOT_LEVELS[lvl]
        lbl_surf = font_bold.render(info["name"], True, fg)
        elo_surf = font_small.render(f"~{info['elo']}", True, sub_fg)
        screen.blit(lbl_surf, (rect.x + 10, rect.y + 8))
        screen.blit(elo_surf, (rect.x + 10, rect.y + 31))

    details_y = grid_top + rows * (card_h + gap_y) + 8
    details_rect = pygame.Rect(panel_x, details_y, panel_w, 72)
    pygame.draw.rect(screen, BG_PANEL, details_rect, border_radius=10)
    pygame.draw.rect(screen, (68, 64, 59), details_rect, width=1, border_radius=10)

    sel_info = BOT_LEVELS[selected_bot_level]
    badge_col = ACCENT_PURPLE if selected_bot_level == 15 else (ACCENT_RED if selected_bot_level == 1 else ACCENT_BLUE)
    head_txt = f"{sel_info['name']}  ({sel_info['elo']})"
    screen.blit(font_bold.render(head_txt, True, badge_col), (details_rect.x + 16, details_rect.y + 12))
    screen.blit(font_small.render(sel_info["desc"], True, TEXT_MUTED), (details_rect.x + 16, details_rect.y + 40))

    btn_y = details_rect.bottom + 14
    btn_start_bot.update(panel_x, btn_y, panel_w, 50)
    btn_back_menu.update(panel_x, btn_y + 60, panel_w, 40)

    start_bg = ACCENT_PURPLE if selected_bot_level == 15 else (ACCENT_RED if selected_bot_level == 1 else ACCENT_BLUE)
    start_hov = (182, 130, 248) if selected_bot_level == 15 else ((238, 80, 80) if selected_bot_level == 1 else ACCENT_BLUE_HOVER)

    draw_button(screen, btn_start_bot, f"Play vs. {sel_info['name']}", font_bold, mouse_pos, bg=start_bg, hover=start_hov, text_col=(255, 255, 255))
    draw_button(screen, btn_back_menu, "Back to Main Menu (M)", font_small, mouse_pos)

    btn_exit.update(24, 24, 150, 38)
    draw_button(screen, btn_exit, "Exit (Esc)", font_small, mouse_pos)


def draw_setup_ui(
    screen, win_w, win_h, board_x, board_y, board_size, sq_size,
    setup_board, setup_flipped, setup_tool, setup_turn, setup_bot_level, setup_status_msg,
    mouse_pos, fonts, palette_rects, setup_btns, btn_exit
):
    _, font_title, font_bold, font_med, font_small, font_coord = fonts
    screen.fill(BG_MAIN)

    bar_h = 44
    top_bar_rect = pygame.Rect(board_x, board_y - bar_h - 6, board_size, bar_h)
    bot_bar_rect = pygame.Rect(board_x, board_y + board_size + 6, board_size, bar_h)

    # Top & Bottom Setup Helper Bars
    pygame.draw.rect(screen, BG_PANEL, top_bar_rect, border_radius=6)
    screen.blit(font_bold.render("Board Editor — Left-Click / Drag to Place • Right-Click to Erase", True, TEXT_PRIMARY), (top_bar_rect.x + 14, top_bar_rect.y + 11))

    pygame.draw.rect(screen, BG_PANEL, bot_bar_rect, border_radius=6)
    tool_label = "Selected Tool: Eraser (Remove Piece)" if setup_tool == ("Erase", "Erase") else f"Selected Tool: {setup_tool[0]} {setup_tool[1]}"
    screen.blit(font_bold.render(tool_label, True, ACCENT_GOLD), (bot_bar_rect.x + 14, bot_bar_rect.y + 11))

    # 8x8 Board
    board_border = pygame.Rect(board_x - 3, board_y - 3, board_size + 6, board_size + 6)
    pygame.draw.rect(screen, (55, 52, 48), board_border, border_radius=4)

    for disp_r in range(ROWS):
        for disp_c in range(COLS):
            r = (7 - disp_r) if setup_flipped else disp_r
            c = (7 - disp_c) if setup_flipped else disp_c
            is_light = (r + c) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE

            sq_rect = pygame.Rect(board_x + disp_c * sq_size, board_y + disp_r * sq_size, sq_size, sq_size)
            pygame.draw.rect(screen, color, sq_rect)

            if sq_rect.collidepoint(mouse_pos):
                hover_surf = pygame.Surface((sq_size, sq_size), pygame.SRCALPHA)
                hover_surf.fill((255, 255, 255, 45))
                screen.blit(hover_surf, sq_rect.topleft)

            coord_col = DARK_SQUARE if is_light else LIGHT_SQUARE
            if disp_c == 0:
                rank_surf = font_coord.render(str(8 - r), True, coord_col)
                screen.blit(rank_surf, (sq_rect.x + 4, sq_rect.y + 3))
            if disp_r == 7:
                file_surf = font_coord.render(chr(ord('a') + c), True, coord_col)
                screen.blit(file_surf, (sq_rect.right - file_surf.get_width() - 4, sq_rect.bottom - file_surf.get_height() - 2))

            piece = setup_board[r][c]
            if piece is not None:
                draw_piece_at_pixel(screen, sq_rect.centerx, sq_rect.centery, piece, sq_size)

    # Right Sidebar Editor Panel
    panel_x = board_x + board_size + 28
    panel_w = min(400, win_w - panel_x - 28)
    if panel_w >= 240:
        panel_y = top_bar_rect.y
        panel_h = bot_bar_rect.bottom - top_bar_rect.y
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(screen, BG_PANEL, panel_rect, border_radius=10)

        header_rect = pygame.Rect(panel_x, panel_y, panel_w, 50)
        pygame.draw.rect(screen, BG_PANEL_HEADER, header_rect, border_top_left_radius=10, border_top_right_radius=10)
        screen.blit(font_title.render("Position Setup", True, TEXT_PRIMARY), (panel_x + 18, panel_y + 12))

        # Piece Palette Grid (White Row + Black Row)
        piece_order = ["Tacker", "Diamond", "Hop", "Hook", "Master", "King"]
        cell_gap = 6
        cell_size = (panel_w - 28 - 5 * cell_gap) // 6
        pal_start_x = panel_x + 14
        white_row_y = panel_y + 62
        black_row_y = white_row_y + cell_size + 8

        for col_idx, p_name in enumerate(piece_order):
            for color_name, row_y in (("White", white_row_y), ("Black", black_row_y)):
                key = (color_name, p_name)
                rect = palette_rects[key]
                rect.update(pal_start_x + col_idx * (cell_size + cell_gap), row_y, cell_size, cell_size)
                is_sel = (setup_tool == key)
                is_hov = rect.collidepoint(mouse_pos)
                bg = ACCENT_GREEN if is_sel else (BTN_HOVER if is_hov else BG_PANEL_HEADER)
                pygame.draw.rect(screen, bg, rect, border_radius=8)
                pygame.draw.rect(screen, (75, 71, 65), rect, width=1, border_radius=8)
                draw_piece_at_pixel(screen, rect.centerx, rect.centery, Piece(color_name, p_name), int(cell_size * 0.84))

        # Eraser & Quick Board Action Buttons
        row1_y = black_row_y + cell_size + 12
        half_w = (panel_w - 34) // 2

        erase_key = ("Erase", "Erase")
        erase_rect = palette_rects[erase_key]
        erase_rect.update(panel_x + 14, row1_y, half_w, 38)
        is_erase_sel = (setup_tool == erase_key)
        draw_button(
            screen, erase_rect, "Eraser Tool", font_small, mouse_pos,
            bg=ACCENT_RED if is_erase_sel else BTN_BG,
            hover=(238, 80, 80) if is_erase_sel else BTN_HOVER,
            text_col=(255, 255, 255)
        )

        setup_btns["flip"].update(panel_x + 20 + half_w, row1_y, half_w, 38)
        draw_button(screen, setup_btns["flip"], "Flip Board", font_small, mouse_pos)

        row2_y = row1_y + 46
        setup_btns["start_pos"].update(panel_x + 14, row2_y, half_w, 38)
        setup_btns["clear"].update(panel_x + 20 + half_w, row2_y, half_w, 38)
        draw_button(screen, setup_btns["start_pos"], "Starting Position", font_small, mouse_pos)
        draw_button(screen, setup_btns["clear"], "Clear Board", font_small, mouse_pos)

        # Turn & Bluechair Difficulty Controls
        row3_y = row2_y + 52
        setup_btns["turn"].update(panel_x + 14, row3_y, panel_w - 28, 40)
        turn_bg = (235, 235, 235) if setup_turn == "White" else (48, 46, 43)
        turn_fg = (20, 20, 20) if setup_turn == "White" else (240, 240, 240)
        draw_button(screen, setup_btns["turn"], f"Side to Move: {setup_turn} (Click to Toggle)", font_small, mouse_pos, bg=turn_bg, hover=turn_bg, text_col=turn_fg)

        row4_y = row3_y + 48
        arrow_w = 44
        setup_btns["bot_prev"].update(panel_x + 14, row4_y, arrow_w, 38)
        setup_btns["bot_next"].update(panel_x + panel_w - 14 - arrow_w, row4_y, arrow_w, 38)
        mid_rect = pygame.Rect(panel_x + 14 + arrow_w + 6, row4_y, panel_w - 28 - 2 * arrow_w - 12, 38)
        pygame.draw.rect(screen, BG_PANEL_HEADER, mid_rect, border_radius=8)
        b_info = BOT_LEVELS[setup_bot_level]
        bot_lbl = font_small.render(f"{b_info['name']} ({b_info['elo']})", True, ACCENT_BLUE)
        screen.blit(bot_lbl, bot_lbl.get_rect(center=mid_rect.center))
        draw_button(screen, setup_btns["bot_prev"], "<", font_bold, mouse_pos)
        draw_button(screen, setup_btns["bot_next"], ">", font_bold, mouse_pos)

        # Validation Warning / Status Message
        if setup_status_msg:
            warn_y = row4_y + 46
            warn_surf = font_small.render(setup_status_msg, True, ACCENT_RED)
            screen.blit(warn_surf, warn_surf.get_rect(center=(panel_x + panel_w // 2, warn_y + 10)))

        # Launch & Back Buttons at Bottom
        btn_y1 = panel_rect.bottom - 156
        btn_y2 = panel_rect.bottom - 104
        btn_y3 = panel_rect.bottom - 52

        setup_btns["play_bot"].update(panel_x + 14, btn_y1, panel_w - 28, 42)
        setup_btns["play_person"].update(panel_x + 14, btn_y2, panel_w - 28, 42)
        setup_btns["back_menu"].update(panel_x + 14, btn_y3, panel_w - 28, 42)

        draw_button(screen, setup_btns["play_bot"], f"Play vs. {b_info['name']}", font_bold, mouse_pos, bg=ACCENT_GREEN, hover=ACCENT_GREEN_HOVER, text_col=(20, 20, 20))
        draw_button(screen, setup_btns["play_person"], "Play in Person / Analysis", font_small, mouse_pos, bg=ACCENT_BLUE, hover=ACCENT_BLUE_HOVER, text_col=(255, 255, 255))
        draw_button(screen, setup_btns["back_menu"], "Back to Menu (M)", font_small, mouse_pos)

    btn_exit.update(24, 24, 150, 38)
    draw_button(screen, btn_exit, "Exit (Esc)", font_small, mouse_pos)


def draw_game_ui(
    screen, win_w, win_h, board_x, board_y, board_size, sq_size,
    board, selected_sq, valid_moves, is_premove_selection, premove_queue,
    last_move, dragging_piece, active_anim, mouse_pos,
    current_turn, white_check, black_check, game_over_msg, move_history,
    game_mode, bot_level, fonts, btn_menu, btn_reset, btn_resign, btn_exit
):
    _, font_title, font_bold, font_med, font_small, font_coord = fonts
    screen.fill(BG_MAIN)

    white_king_pos = find_king(board, "White")
    black_king_pos = find_king(board, "Black")

    bar_h = 44
    top_bar_rect = pygame.Rect(board_x, board_y - bar_h - 6, board_size, bar_h)
    bot_bar_rect = pygame.Rect(board_x, board_y + board_size + 6, board_size, bar_h)

    if game_mode == "bots":
        b_info = BOT_LEVELS[bot_level]
        black_name = f"{b_info['name']} ({b_info['elo']})"
        white_name = "You (White)"
    elif game_mode == "analysis":
        black_name = "Black (Analysis)"
        white_name = "White (Analysis)"
    else:
        black_name = "Black"
        white_name = "White"

    pygame.draw.rect(screen, BG_PANEL, top_bar_rect, border_radius=6)
    pygame.draw.rect(screen, BLACK_FILL, (top_bar_rect.x + 10, top_bar_rect.y + 8, 28, 28), border_radius=4)
    pygame.draw.rect(screen, BLACK_OUTLINE, (top_bar_rect.x + 10, top_bar_rect.y + 8, 28, 28), width=2, border_radius=4)
    black_label = black_name + ("  •  IN CHECK" if black_check else "")
    screen.blit(font_bold.render(black_label, True, HIGHLIGHT_CHECK if black_check else TEXT_PRIMARY), (top_bar_rect.x + 48, top_bar_rect.y + 11))

    if current_turn == "Black" and not game_over_msg:
        pill = pygame.Rect(top_bar_rect.right - 135, top_bar_rect.y + 9, 123, 26)
        pygame.draw.rect(screen, ACCENT_GOLD if game_mode == "bots" else ACCENT_GREEN, pill, border_radius=5)
        t_surf = font_small.render("THINKING..." if game_mode == "bots" else "TURN", True, (20, 20, 20))
        screen.blit(t_surf, t_surf.get_rect(center=pill.center))

    pygame.draw.rect(screen, BG_PANEL, bot_bar_rect, border_radius=6)
    pygame.draw.rect(screen, WHITE_FILL, (bot_bar_rect.x + 10, bot_bar_rect.y + 8, 28, 28), border_radius=4)
    pygame.draw.rect(screen, WHITE_OUTLINE, (bot_bar_rect.x + 10, bot_bar_rect.y + 8, 28, 28), width=2, border_radius=4)
    white_label = white_name + ("  •  IN CHECK" if white_check else "")
    screen.blit(font_bold.render(white_label, True, HIGHLIGHT_CHECK if white_check else TEXT_PRIMARY), (bot_bar_rect.x + 48, bot_bar_rect.y + 11))

    if premove_queue:
        pill = pygame.Rect(bot_bar_rect.right - 190, bot_bar_rect.y + 9, 178, 26)
        pygame.draw.rect(screen, ACCENT_RED, pill, border_radius=5)
        t_surf = font_small.render(f"PREMOVES: {len(premove_queue)} (R-Click Clear)", True, (255, 255, 255))
        screen.blit(t_surf, t_surf.get_rect(center=pill.center))
    elif current_turn == "White" and not game_over_msg:
        pill = pygame.Rect(bot_bar_rect.right - 110, bot_bar_rect.y + 9, 98, 26)
        pygame.draw.rect(screen, ACCENT_GREEN, pill, border_radius=5)
        t_surf = font_small.render("TURN", True, (20, 20, 20))
        screen.blit(t_surf, t_surf.get_rect(center=pill.center))

    board_border = pygame.Rect(board_x - 3, board_y - 3, board_size + 6, board_size + 6)
    pygame.draw.rect(screen, (55, 52, 48), board_border, border_radius=4)

    for r in range(ROWS):
        for c in range(COLS):
            is_light = (r + c) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            if selected_sq == (r, c):
                color = HIGHLIGHT_SELECTED
            elif (white_check and (r, c) == white_king_pos) or (black_check and (r, c) == black_king_pos):
                color = HIGHLIGHT_CHECK

            sq_rect = pygame.Rect(board_x + c * sq_size, board_y + r * sq_size, sq_size, sq_size)
            pygame.draw.rect(screen, color, sq_rect)

            coord_col = DARK_SQUARE if is_light else LIGHT_SQUARE
            if c == 0:
                rank_surf = font_coord.render(str(8 - r), True, coord_col)
                screen.blit(rank_surf, (sq_rect.x + 4, sq_rect.y + 3))
            if r == 7:
                file_surf = font_coord.render(chr(ord('a') + c), True, coord_col)
                screen.blit(file_surf, (sq_rect.right - file_surf.get_width() - 4, sq_rect.bottom - file_surf.get_height() - 2))

    overlay = pygame.Surface((board_size, board_size), pygame.SRCALPHA)

    if last_move is not None:
        for (lr, lc) in last_move:
            pygame.draw.rect(overlay, HIGHLIGHT_LAST_MOVE, (lc * sq_size, lr * sq_size, sq_size, sq_size))

    for idx, (pm_start, pm_end) in enumerate(premove_queue):
        for (pr, pc) in (pm_start, pm_end):
            pygame.draw.rect(overlay, HIGHLIGHT_PREMOVE, (pc * sq_size, pr * sq_size, sq_size, sq_size))
        if len(premove_queue) > 1:
            er, ec = pm_end
            badge_surf = font_coord.render(str(idx + 1), True, (255, 255, 255))
            overlay.blit(badge_surf, (ec * sq_size + sq_size - badge_surf.get_width() - 5, er * sq_size + 4))

    for (mr, mc), captures in valid_moves.items():
        cx = mc * sq_size + sq_size // 2
        cy = mr * sq_size + sq_size // 2

        if is_premove_selection:
            if captures:
                pygame.draw.circle(overlay, PREMOVE_RING, (cx, cy), int(sq_size * 0.38), width=max(3, sq_size // 18))
            else:
                pygame.draw.circle(overlay, PREMOVE_DOT, (cx, cy), max(9, sq_size // 6))
        else:
            if captures:
                pygame.draw.rect(overlay, DARK_CAPTURE_TINT, (mc * sq_size, mr * sq_size, sq_size, sq_size))
                pygame.draw.circle(overlay, DARK_CAPTURE_RING, (cx, cy), int(sq_size * 0.38), width=max(3, sq_size // 18))
                for (cr, cc) in captures:
                    cap_x = cc * sq_size + sq_size // 2
                    cap_y = cr * sq_size + sq_size // 2
                    pygame.draw.circle(overlay, DARK_CAPTURE_RING, (cap_x, cap_y), max(8, sq_size // 7))
            else:
                pygame.draw.circle(overlay, DARK_MOVE_DOT, (cx, cy), max(9, sq_size // 6))

    screen.blit(overlay, (board_x, board_y))

    anim_piece = active_anim["piece"] if active_anim is not None else None
    for r in range(ROWS):
        for c in range(COLS):
            piece = board[r][c]
            if piece is not None and piece is not dragging_piece and piece is not anim_piece:
                cx = board_x + c * sq_size + sq_size // 2
                cy = board_y + r * sq_size + sq_size // 2
                draw_piece_at_pixel(screen, cx, cy, piece, sq_size, font_coord)

    if active_anim is not None and anim_piece is not dragging_piece:
        elapsed = time.perf_counter() - active_anim["start_time"]
        progress = ease_out_cubic(elapsed / active_anim["duration"])
        sr, sc = active_anim["start_sq"]
        er, ec = active_anim["end_sq"]
        start_px = board_x + sc * sq_size + sq_size // 2
        start_py = board_y + sr * sq_size + sq_size // 2
        end_px = board_x + ec * sq_size + sq_size // 2
        end_py = board_y + er * sq_size + sq_size // 2
        cur_px = int(round(start_px + (end_px - start_px) * progress))
        cur_py = int(round(start_py + (end_py - start_py) * progress))
        draw_piece_at_pixel(screen, cur_px, cur_py, anim_piece, sq_size, font_coord)

    if dragging_piece is not None:
        mx, my = mouse_pos
        draw_piece_at_pixel(screen, mx, my, dragging_piece, sq_size, font_coord)

    panel_x = board_x + board_size + 28
    panel_w = min(380, win_w - panel_x - 28)
    if panel_w >= 220:
        panel_y = top_bar_rect.y
        panel_h = bot_bar_rect.bottom - top_bar_rect.y
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(screen, BG_PANEL, panel_rect, border_radius=10)

        mode_titles = {
            "bots": BOT_LEVELS[bot_level]["name"],
            "person": "Play in Person",
            "analysis": "Analysis Board",
        }
        header_rect = pygame.Rect(panel_x, panel_y, panel_w, 52)
        pygame.draw.rect(screen, BG_PANEL_HEADER, header_rect, border_top_left_radius=10, border_top_right_radius=10)
        title_surf = font_title.render(mode_titles.get(game_mode, "Geometric Chess"), True, TEXT_PRIMARY)
        screen.blit(title_surf, (panel_x + 18, panel_y + 13))

        status_y = panel_y + 62
        if game_over_msg:
            banner_rect = pygame.Rect(panel_x + 14, status_y, panel_w - 28, 44)
            pygame.draw.rect(screen, ACCENT_GREEN, banner_rect, border_radius=7)
            msg_surf = font_bold.render(game_over_msg, True, (20, 20, 20))
            screen.blit(msg_surf, msg_surf.get_rect(center=banner_rect.center))
        elif premove_queue:
            pm_list_str = ", ".join(f"{sq_to_algebraic(s)}{sq_to_algebraic(e)}" for s, e in premove_queue)
            status_txt = f"Queued: {pm_list_str}"
            screen.blit(font_small.render(status_txt, True, ACCENT_RED), (panel_x + 18, status_y + 12))
        else:
            status_txt = f"{current_turn} to move"
            if white_check or black_check:
                status_txt += "  (CHECK!)"
            screen.blit(font_med.render(status_txt, True, ACCENT_GOLD if (white_check or black_check) else TEXT_MUTED), (panel_x + 18, status_y + 10))

        list_top = status_y + 56
        list_bottom = panel_rect.bottom - 172
        list_h = max(100, list_bottom - list_top)
        list_rect = pygame.Rect(panel_x + 14, list_top, panel_w - 28, list_h)
        pygame.draw.rect(screen, BG_PANEL_HEADER, list_rect, border_radius=8)

        col_num_x = list_rect.x + 14
        col_w_x = list_rect.x + 62
        col_b_x = list_rect.x + (list_rect.width // 2) + 24

        screen.blit(font_small.render("#", True, TEXT_MUTED), (col_num_x, list_rect.y + 8))
        screen.blit(font_small.render("White", True, TEXT_MUTED), (col_w_x, list_rect.y + 8))
        screen.blit(font_small.render("Black", True, TEXT_MUTED), (col_b_x, list_rect.y + 8))
        pygame.draw.line(screen, (60, 57, 52), (list_rect.x + 8, list_rect.y + 30), (list_rect.right - 8, list_rect.y + 30), 1)

        pairs = []
        for i in range(0, len(move_history), 2):
            w_mv = move_history[i]
            b_mv = move_history[i + 1] if i + 1 < len(move_history) else ""
            pairs.append((i // 2 + 1, w_mv, b_mv))

        row_h = 28
        max_visible_rows = (list_rect.height - 38) // row_h
        visible_pairs = pairs[-max_visible_rows:] if max_visible_rows > 0 else []

        for idx, (turn_num, w_mv, b_mv) in enumerate(visible_pairs):
            ry = list_rect.y + 34 + idx * row_h
            if idx % 2 == 1:
                pygame.draw.rect(screen, BG_ROW_ALT, (list_rect.x + 4, ry, list_rect.width - 8, row_h), border_radius=4)
            screen.blit(font_small.render(f"{turn_num}.", True, TEXT_MUTED), (col_num_x, ry + 5))
            screen.blit(font_med.render(w_mv, True, TEXT_PRIMARY), (col_w_x, ry + 4))
            screen.blit(font_med.render(b_mv, True, TEXT_PRIMARY), (col_b_x, ry + 4))

        btn_y1 = panel_rect.bottom - 156
        btn_y2 = panel_rect.bottom - 104
        btn_y3 = panel_rect.bottom - 52
        half_w = (panel_w - 38) // 2

        btn_reset.update(panel_x + 14, btn_y1, half_w, 42)
        btn_resign.update(panel_x + 24 + half_w, btn_y1, half_w, 42)
        btn_menu.update(panel_x + 14, btn_y2, panel_w - 28, 42)
        btn_exit.update(panel_x + 14, btn_y3, panel_w - 28, 42)

        draw_button(screen, btn_reset, "New Game (R)", font_small, mouse_pos, bg=ACCENT_GREEN, hover=ACCENT_GREEN_HOVER, text_col=(20, 20, 20))
        draw_button(screen, btn_resign, "Resign (G)", font_small, mouse_pos)
        draw_button(screen, btn_menu, "Back to Menu (M)", font_small, mouse_pos)
        draw_button(screen, btn_exit, "Exit Fullscreen (Esc)", font_small, mouse_pos)


def main():
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    win_w, win_h = screen.get_size()
    pygame.display.set_caption("Geometric Chess")

    usable_h = win_h - 140
    sq_size = max(56, min(usable_h // 8, (win_w - 440) // 8))
    board_size = sq_size * 8

    sidebar_w = 340
    total_group_w = board_size + 28 + sidebar_w
    board_x = max(24, (win_w - total_group_w) // 2)
    board_y = (win_h - board_size) // 2

    fonts = (
        pygame.font.SysFont("arial", 52, bold=True),
        pygame.font.SysFont("arial", 22, bold=True),
        pygame.font.SysFont("arial", 18, bold=True),
        pygame.font.SysFont("arial", 16),
        pygame.font.SysFont("arial", 14, bold=True),
        pygame.font.SysFont("arial", max(11, sq_size // 6), bold=True),
    )

    emoji_font = None
    for fam in ("segoe ui emoji", "apple color emoji", "noto color emoji", "symbola"):
        if fam in pygame.font.get_fonts():
            emoji_font = pygame.font.SysFont(fam, 26)
            break

    clock = pygame.time.Clock()

    # App States: "menu", "bot_select", "setup", or "playing"
    app_state = "menu"
    game_mode = "person"
    selected_bot_level = 8
    menu_notice = None

    # Setup Editor State
    setup_board = create_board()
    setup_flipped = False
    setup_tool = ("White", "Master")
    setup_turn = "White"
    setup_status_msg = None
    setup_painting = False

    board = create_board()
    current_turn = "White"
    selected_sq = None
    valid_moves = {}
    is_premove_selection = False
    premove_queue = []
    last_move = None
    dragging_piece = None
    active_anim = None
    game_over_msg = None
    move_history = []
    position_counts = {}

    white_check = False
    black_check = False
    bot_timer = 0

    menu_buttons = {
        "bots": pygame.Rect(0, 0, 10, 10),
        "online": pygame.Rect(0, 0, 10, 10),
        "person": pygame.Rect(0, 0, 10, 10),
        "analysis": pygame.Rect(0, 0, 10, 10),
        "setup": pygame.Rect(0, 0, 10, 10),
    }
    level_rects = {lvl: pygame.Rect(0, 0, 10, 10) for lvl in range(1, 16)}
    btn_start_bot = pygame.Rect(0, 0, 10, 10)
    btn_back_menu = pygame.Rect(0, 0, 10, 10)

    palette_rects = {
        (c, p): pygame.Rect(0, 0, 10, 10)
        for c in ("White", "Black")
        for p in ("Tacker", "Diamond", "Hop", "Hook", "Master", "King")
    }
    palette_rects[("Erase", "Erase")] = pygame.Rect(0, 0, 10, 10)
    setup_btns = {
        "flip": pygame.Rect(0, 0, 10, 10),
        "start_pos": pygame.Rect(0, 0, 10, 10),
        "clear": pygame.Rect(0, 0, 10, 10),
        "turn": pygame.Rect(0, 0, 10, 10),
        "bot_prev": pygame.Rect(0, 0, 10, 10),
        "bot_next": pygame.Rect(0, 0, 10, 10),
        "play_bot": pygame.Rect(0, 0, 10, 10),
        "play_person": pygame.Rect(0, 0, 10, 10),
        "back_menu": pygame.Rect(0, 0, 10, 10),
    }

    btn_menu = pygame.Rect(0, 0, 10, 10)
    btn_reset = pygame.Rect(0, 0, 10, 10)
    btn_resign = pygame.Rect(0, 0, 10, 10)
    btn_exit = pygame.Rect(0, 0, 10, 10)

    def start_mode(mode, custom_board=None, starting_turn="White"):
        nonlocal app_state, game_mode, board, current_turn, selected_sq, valid_moves
        nonlocal is_premove_selection, premove_queue, last_move, dragging_piece, active_anim
        nonlocal game_over_msg, move_history, position_counts, white_check, black_check, bot_timer
        game_mode = mode
        app_state = "playing"
        board = clone_board(custom_board) if custom_board is not None else create_board()
        current_turn = starting_turn
        selected_sq = None
        valid_moves = {}
        is_premove_selection = False
        premove_queue = []
        last_move = None
        dragging_piece = None
        active_anim = None
        game_over_msg = None
        move_history = []
        position_counts = {}
        evaluate_board_state(current_turn)
        if game_mode == "bots" and current_turn == "Black" and not game_over_msg:
            bot_timer = 24
        else:
            bot_timer = 0

    def evaluate_board_state(next_turn):
        nonlocal white_check, black_check, game_over_msg
        white_check = is_in_check(board, "White")
        black_check = is_in_check(board, "Black")

        h = board_hash(board, next_turn)
        position_counts[h] = position_counts.get(h, 0) + 1

        if not has_any_legal_moves(board, next_turn):
            opponent = "Black" if next_turn == "White" else "White"
            if (next_turn == "White" and white_check) or (next_turn == "Black" and black_check):
                game_over_msg = f"CHECKMATE! {opponent} Wins!"
            else:
                game_over_msg = f"STALEMATE! {opponent} Wins!"
        elif position_counts[h] >= 3:
            game_over_msg = "DRAW by Threefold Repetition!"

    def apply_setup_at_pixel(mx, my, erase_override=False):
        nonlocal setup_status_msg
        if not (board_x <= mx < board_x + board_size and board_y <= my < board_y + board_size):
            return
        disp_r = (my - board_y) // sq_size
        disp_c = (mx - board_x) // sq_size
        r = (7 - disp_r) if setup_flipped else disp_r
        c = (7 - disp_c) if setup_flipped else disp_c
        setup_status_msg = None

        if erase_override or setup_tool == ("Erase", "Erase"):
            setup_board[r][c] = None
        else:
            color_name, piece_name = setup_tool
            # Enforce max 1 King per color like Chess.com's board editor
            if piece_name == "King":
                for rr in range(ROWS):
                    for cc in range(COLS):
                        existing = setup_board[rr][cc]
                        if existing is not None and existing.color == color_name and existing.name == "King":
                            setup_board[rr][cc] = None
            new_p = Piece(color_name, piece_name)
            # Mark Tackers placed off their home rank as already moved
            if piece_name == "Tacker":
                home_r = 6 if color_name == "White" else 1
                new_p.has_moved = (r != home_r)
            setup_board[r][c] = new_p

    def validate_setup_board():
        w_king = find_king(setup_board, "White")
        b_king = find_king(setup_board, "Black")
        if w_king is None or b_king is None:
            return "Both White and Black must have a King on the board!"
        opp_turn = "Black" if setup_turn == "White" else "White"
        if is_in_check(setup_board, opp_turn):
            return f"Invalid: {opp_turn}'s King is already in check on {setup_turn}'s turn!"
        return None

    def sync_dragged_piece_after_turn():
        nonlocal dragging_piece, selected_sq, valid_moves, is_premove_selection
        if dragging_piece is None:
            selected_sq = None
            valid_moves = {}
            is_premove_selection = False
            return

        if game_over_msg:
            dragging_piece = None
            selected_sq = None
            valid_moves = {}
            is_premove_selection = False
            return

        live_pos = find_piece_position(board, dragging_piece)
        if live_pos is None:
            dragging_piece = None
            selected_sq = None
            valid_moves = {}
            is_premove_selection = False
            return

        is_still_premove = (game_mode == "bots" and current_turn == "Black")
        if not is_still_premove:
            selected_sq = live_pos
            valid_moves = get_legal_moves(board, selected_sq)
            is_premove_selection = False
        else:
            proj = build_projected_board(board, premove_queue)
            proj_pos = find_piece_position(proj, dragging_piece)
            if proj_pos is not None:
                selected_sq = proj_pos
                valid_moves = get_premove_candidates(proj, selected_sq)
                is_premove_selection = True
            else:
                dragging_piece = None
                selected_sq = None
                valid_moves = {}
                is_premove_selection = False

    def execute_move(start_sq, end_sq, captures, animate=True):
        nonlocal current_turn, last_move, bot_timer, active_anim
        sr, sc = start_sq
        er, ec = end_sq
        moving_piece = board[sr][sc]

        for cap_r, cap_c in captures:
            board[cap_r][cap_c] = None

        board[er][ec] = moving_piece
        board[sr][sc] = None
        moving_piece.has_moved = True
        moving_piece.captures += len(captures)
        if can_promote_to_master(moving_piece):
            moving_piece.name = "Master"

        last_move = (start_sq, end_sq)

        if animate:
            active_anim = {
                "piece": moving_piece,
                "start_sq": start_sq,
                "end_sq": end_sq,
                "start_time": time.perf_counter(),
                "duration": MOVE_GLIDE_DURATION,
            }
        else:
            active_anim = None

        current_turn = "Black" if current_turn == "White" else "White"
        evaluate_board_state(current_turn)
        sync_dragged_piece_after_turn()

        move_str = f"{sq_to_algebraic(start_sq)}{sq_to_algebraic(end_sq)}"
        if game_over_msg and game_over_msg.startswith("CHECKMATE"):
            move_str += "#"
        elif white_check or black_check:
            move_str += "+"
        move_history.append(move_str)

        if game_mode == "bots" and current_turn == "Black" and not game_over_msg:
            bot_timer = 24

    def try_trigger_queued_premove():
        nonlocal premove_queue
        if not premove_queue or game_over_msg:
            return

        pm_start, pm_end = premove_queue[0]
        sr, sc = pm_start
        piece = board[sr][sc]

        if piece is None or piece.color != current_turn:
            premove_queue.clear()
            sync_dragged_piece_after_turn()
            return

        legal_now = get_legal_moves(board, pm_start)
        if pm_end in legal_now:
            premove_queue.pop(0)
            execute_move(pm_start, pm_end, legal_now[pm_end], animate=True)
        else:
            premove_queue.clear()
            sync_dragged_piece_after_turn()

    while True:
        clock.tick(60)
        mouse_pos = pygame.mouse.get_pos()

        if active_anim is not None:
            if time.perf_counter() - active_anim["start_time"] >= active_anim["duration"]:
                active_anim = None

        if app_state == "playing" and game_mode == "bots" and current_turn == "Black" and not game_over_msg:
            if bot_timer > 0:
                bot_timer -= 1
            else:
                bot_choice = pick_bot_move(board, "Black", selected_bot_level)
                if bot_choice is not None:
                    b_start, b_end, b_caps = bot_choice
                    execute_move(b_start, b_end, b_caps, animate=True)
                    if current_turn == "White" and premove_queue and not game_over_msg:
                        try_trigger_queued_premove()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif app_state in ("bot_select", "setup"):
                    if event.key == pygame.K_m:
                        app_state = "menu"
                    elif app_state == "bot_select":
                        if event.key == pygame.K_RETURN:
                            start_mode("bots")
                        elif event.key == pygame.K_LEFT and selected_bot_level > 1:
                            selected_bot_level -= 1
                        elif event.key == pygame.K_RIGHT and selected_bot_level < 15:
                            selected_bot_level += 1
                elif app_state == "playing":
                    if event.key == pygame.K_r:
                        start_mode(game_mode)
                    elif event.key == pygame.K_m:
                        app_state = "menu"
                        menu_notice = None
                    elif event.key == pygame.K_c:
                        premove_queue.clear()
                        sync_dragged_piece_after_turn()
                    elif event.key == pygame.K_g and not game_over_msg:
                        winner = "Black" if current_turn == "White" else "White"
                        game_over_msg = f"{current_turn} Resigned — {winner} Wins!"
                        premove_queue.clear()
                        selected_sq = None
                        valid_moves = {}
                        dragging_piece = None
                        active_anim = None

            if event.type == pygame.MOUSEMOTION and app_state == "setup" and setup_painting:
                mx, my = event.pos
                apply_setup_at_pixel(mx, my)

            if event.type == pygame.MOUSEBUTTONUP and app_state == "setup":
                setup_painting = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                # Right-click in Setup erases square; in Playing clears premoves
                if event.button == 3:
                    if app_state == "setup":
                        apply_setup_at_pixel(mx, my, erase_override=True)
                    elif app_state == "playing":
                        premove_queue.clear()
                        sync_dragged_piece_after_turn()
                    continue

                if event.button == 1:
                    if btn_exit.collidepoint((mx, my)):
                        pygame.quit()
                        sys.exit()

                    if app_state == "menu":
                        if menu_buttons["bots"].collidepoint((mx, my)):
                            app_state = "bot_select"
                            menu_notice = None
                        elif menu_buttons["person"].collidepoint((mx, my)):
                            start_mode("person")
                        elif menu_buttons["analysis"].collidepoint((mx, my)):
                            start_mode("analysis")
                        elif menu_buttons["setup"].collidepoint((mx, my)):
                            app_state = "setup"
                            setup_status_msg = None
                            menu_notice = None
                        elif menu_buttons["online"].collidepoint((mx, my)):
                            menu_notice = "Online matchmaking requires a server — try Bots or Play in Person!"
                        continue

                    if app_state == "bot_select":
                        for lvl, rect in level_rects.items():
                            if rect.collidepoint((mx, my)):
                                selected_bot_level = lvl
                                break
                        if btn_start_bot.collidepoint((mx, my)):
                            start_mode("bots")
                        elif btn_back_menu.collidepoint((mx, my)):
                            app_state = "menu"
                        continue

                    if app_state == "setup":
                        for key, rect in palette_rects.items():
                            if rect.collidepoint((mx, my)):
                                setup_tool = key
                                setup_status_msg = None
                                break
                        if setup_btns["flip"].collidepoint((mx, my)):
                            setup_flipped = not setup_flipped
                        elif setup_btns["start_pos"].collidepoint((mx, my)):
                            setup_board = create_board()
                            setup_status_msg = None
                        elif setup_btns["clear"].collidepoint((mx, my)):
                            setup_board = create_empty_board()
                            setup_status_msg = None
                        elif setup_btns["turn"].collidepoint((mx, my)):
                            setup_turn = "Black" if setup_turn == "White" else "White"
                            setup_status_msg = None
                        elif setup_btns["bot_prev"].collidepoint((mx, my)):
                            selected_bot_level = 15 if selected_bot_level == 1 else selected_bot_level - 1
                        elif setup_btns["bot_next"].collidepoint((mx, my)):
                            selected_bot_level = 1 if selected_bot_level == 15 else selected_bot_level + 1
                        elif setup_btns["play_bot"].collidepoint((mx, my)):
                            err = validate_setup_board()
                            if err:
                                setup_status_msg = err
                            else:
                                start_mode("bots", custom_board=setup_board, starting_turn=setup_turn)
                        elif setup_btns["play_person"].collidepoint((mx, my)):
                            err = validate_setup_board()
                            if err:
                                setup_status_msg = err
                            else:
                                start_mode("person", custom_board=setup_board, starting_turn=setup_turn)
                        elif setup_btns["back_menu"].collidepoint((mx, my)):
                            app_state = "menu"
                        elif board_x <= mx < board_x + board_size and board_y <= my < board_y + board_size:
                            setup_painting = True
                            apply_setup_at_pixel(mx, my)
                        continue

                    if btn_reset.collidepoint((mx, my)):
                        start_mode(game_mode)
                        continue
                    elif btn_menu.collidepoint((mx, my)):
                        app_state = "menu"
                        menu_notice = None
                        continue
                    elif btn_resign.collidepoint((mx, my)) and not game_over_msg:
                        winner = "Black" if current_turn == "White" else "White"
                        game_over_msg = f"{current_turn} Resigned — {winner} Wins!"
                        premove_queue.clear()
                        selected_sq = None
                        valid_moves = {}
                        dragging_piece = None
                        active_anim = None
                        continue

                    if not game_over_msg and board_x <= mx < board_x + board_size and board_y <= my < board_y + board_size:
                        clicked_r = (my - board_y) // sq_size
                        clicked_c = (mx - board_x) // sq_size
                        clicked_sq = (clicked_r, clicked_c)

                        is_premove_turn = (game_mode == "bots" and current_turn == "Black")

                        if not is_premove_turn:
                            if selected_sq is not None and not is_premove_selection and clicked_sq in valid_moves:
                                target_sq = selected_sq
                                caps = valid_moves[clicked_sq]
                                dragging_piece = None
                                execute_move(target_sq, clicked_sq, caps, animate=True)
                            else:
                                piece = board[clicked_r][clicked_c]
                                if piece is not None and piece.color == current_turn:
                                    selected_sq = clicked_sq
                                    valid_moves = get_legal_moves(board, selected_sq)
                                    is_premove_selection = False
                                    dragging_piece = piece
                                else:
                                    selected_sq = None
                                    valid_moves = {}
                                    is_premove_selection = False
                                    dragging_piece = None
                        else:
                            proj_board = build_projected_board(board, premove_queue)
                            if selected_sq is not None and is_premove_selection and clicked_sq in valid_moves:
                                premove_queue.append((selected_sq, clicked_sq))
                                selected_sq = None
                                valid_moves = {}
                                is_premove_selection = False
                                dragging_piece = None
                            else:
                                piece = proj_board[clicked_r][clicked_c]
                                if piece is not None and piece.color == "White":
                                    selected_sq = clicked_sq
                                    valid_moves = get_premove_candidates(proj_board, selected_sq)
                                    is_premove_selection = True
                                    dragging_piece = piece
                                else:
                                    selected_sq = None
                                    valid_moves = {}
                                    is_premove_selection = False
                                    dragging_piece = None

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and app_state == "playing":
                if dragging_piece is not None and selected_sq is not None:
                    mx, my = event.pos
                    if board_x <= mx < board_x + board_size and board_y <= my < board_y + board_size:
                        drop_r = (my - board_y) // sq_size
                        drop_c = (mx - board_x) // sq_size
                        drop_sq = (drop_r, drop_c)

                        if drop_sq in valid_moves:
                            if is_premove_selection:
                                premove_queue.append((selected_sq, drop_sq))
                                selected_sq = None
                                valid_moves = {}
                                is_premove_selection = False
                                dragging_piece = None
                            else:
                                target_sq = selected_sq
                                caps = valid_moves[drop_sq]
                                dragging_piece = None
                                execute_move(target_sq, drop_sq, caps, animate=False)
                                continue
                    dragging_piece = None

        if app_state == "menu":
            draw_main_menu(
                screen, win_w, win_h, board, board_x, board_y, board_size, sq_size,
                mouse_pos, fonts, emoji_font, menu_buttons, btn_exit, menu_notice
            )
        elif app_state == "bot_select":
            draw_bot_select_menu(
                screen, win_w, win_h, board, board_y, board_size, sq_size,
                mouse_pos, fonts, selected_bot_level, level_rects, btn_start_bot, btn_back_menu, btn_exit
            )
        elif app_state == "setup":
            draw_setup_ui(
                screen, win_w, win_h, board_x, board_y, board_size, sq_size,
                setup_board, setup_flipped, setup_tool, setup_turn, selected_bot_level, setup_status_msg,
                mouse_pos, fonts, palette_rects, setup_btns, btn_exit
            )
        else:
            draw_game_ui(
                screen, win_w, win_h, board_x, board_y, board_size, sq_size,
                board, selected_sq, valid_moves, is_premove_selection, premove_queue,
                last_move, dragging_piece, active_anim, mouse_pos,
                current_turn, white_check, black_check, game_over_msg, move_history,
                game_mode, selected_bot_level, fonts, btn_menu, btn_reset, btn_resign, btn_exit
            )

        pygame.display.flip()


if __name__ == "__main__":
    main()