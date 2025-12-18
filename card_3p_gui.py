import sys
import socket
import json
import time
import tkinter as tk
from tkinter import messagebox
import threading
import random
from typing import List, Dict, Union

# ============================================
# 遊戲邏輯函數
# ============================================

def check_win(game_state: Dict) -> Union[str, None]:
    """檢查總勝場數決定最終贏家"""
    if game_state['round'] == 3:
        scores = game_state['total_wins']
        max_wins = max(scores.values())
        winners = [player for player, wins in scores.items() if wins == max_wins]
        
        # 平手條件：如果有玩家贏的次數不是最多（即 max_wins > 1 且多於一人），
        # 這裡簡化為如果多人達到最高分，且最高分>0，則為平局，否則為贏家
        if len(winners) > 1:
            return 'Draw'
        return winners[0]
    return None

def determine_round_winner(moves: Dict, player_roles: List[str]) -> str:
    """根據出牌和選擇（比大/比小）判斷本回合勝者"""
    
    # 範例 moves: {'P1': {'card': 10, 'mode': 'MAX'}, 'P2': {'card': 5, 'mode': 'MIN'}, 'P3': {'card': 12, 'mode': 'MAX'}}
    
    cards = {role: move['card'] for role, move in moves.items()}
    modes = {role: move['mode'] for role, move in moves.items()}
    
    # 1. 計算比大 (MAX) 和比小 (MIN) 的玩家數
    max_players = [role for role, mode in modes.items() if mode == 'MAX']
    min_players = [role for role, mode in modes.items() if mode == 'MIN']
    
    # 2. 判斷勝負模式
    
    # 規則：若兩位以上玩家選擇比小，則出最小數字者獲勝；反之則出最大數字者獲勝
    if len(min_players) >= 2:
        # 比小模式：在所有玩家中，出最小牌者獲勝
        winning_card = min(cards.values())
        winning_players = [role for role, card in cards.items() if card == winning_card]
        return winning_players[0] # 簡單處理：平局時給予其中一人，或設為 Draw
    else:
        # 比大模式：在所有玩家中，出最大牌者獲勝
        winning_card = max(cards.values())
        winning_players = [role for role, card in cards.items() if card == winning_card]
        return winning_players[0]

# ============================================
# 遊戲服務器 (Game Server) - 三人版本
# ============================================

def run_server(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', int(port)))
        server.listen(3) # 等待 3 個連線
        print(f"[GAME SERVER] Listening on {port}")
        
        # 角色列表
        player_roles = ['P1', 'P2', 'P3'] 
        
        # ⚠️ 【修正點】: 使用字典儲存連線，根據 Client 發送的身份來確定角色
        player_conns = {}     # {role: conn}
        player_files = {}     # {role: file_stream}
        
        # 等待三個玩家連接並接收身份
        for i in range(3):
            conn, addr = server.accept()
            
            # 接收 Client 發送的第一條訊息 (即 Client 的角色，例如 "P1\n")
            # 由於 makefile('r') 只能讀取一次，這裡使用一個臨時文件流來讀取角色
            role_file = conn.makefile('r', encoding='utf-8')
            role_line = role_file.readline().strip() 
            
            # 確保角色是 P1, P2 或 P3
            if role_line in player_roles and role_line not in player_conns:
                role = role_line
                # 必須重新建立 file stream 給遊戲主迴圈使用 (因為 role_file 已經讀取過)
                player_conns[role] = conn
                player_files[role] = conn.makefile('r', encoding='utf-8') 
                print(f"Player {i+1} connected: {addr}, Identity: {role}")
            else:
                # 角色不合法或重複，斷開連線 (簡化處理)
                conn.close()
                raise ValueError(f"Invalid or duplicate role received: {role_line}")
        
        # 確保所有角色 (P1, P2, P3) 都已連線
        players_list = [player_conns[role] for role in player_roles]

        # 初始發牌 (牌堆 1-15)
        deck = list(range(1, 16))
        random.shuffle(deck)
        
        player_hands = {
            'P1': sorted(deck[:3]),
            'P2': sorted(deck[3:6]),
            'P3': sorted(deck[6:9])
        }
        
        game_state = {
            'player_hands': player_hands,
            'round': 1,
            'total_wins': {'P1': 0, 'P2': 0, 'P3': 0},
            'current_moves': {}, # {role: {'card': int, 'mode': 'MAX'|'MIN'}}
            'turn': 'ALL', # 同步出牌
            'round_result': None,
            'game_active': True
        }
        
        # 立即將手牌發送給對應的玩家
        for role in player_roles:
            initial_data = {
                'status': 'START',
                'hand': player_hands[role],
                'role': role
            }
            player_conns[role].sendall((json.dumps(initial_data) + "\n").encode())
        
        # --- 遊戲主循環開始 ---
        try:
            while game_state['game_active']:
                # 1. 廣播當前狀態 (回合數，總得分)
                state_to_send = {
                    'round': game_state['round'],
                    'total_wins': game_state['total_wins'],
                    'turn': 'ALL', # 所有玩家行動
                    'round_result': game_state['round_result']
                }
                msg = json.dumps(state_to_send) + "\n"
                
                for p in players_list:
                    p.sendall(msg.encode())
                
                print(f"[Round {game_state['round']}] 等待所有玩家出牌...")
                
                # 2. 接收所有玩家的操作 (同步等待)
                game_state['current_moves'] = {}
                received_count = 0
                input_received = threading.Event()
                
                # 【新增】多執行緒讀取函數
                def get_player_move(role):
                    nonlocal received_count
                    conn_file = player_files[role]
                    try:
                        line = conn_file.readline() # 阻塞讀取
                        if not line:
                            print(f"玩家 {role} 斷線")
                            game_state['game_active'] = False
                            input_received.set()
                            return

                        action_data = json.loads(line.strip()) # 格式: {'card': int, 'mode': 'MAX'|'MIN'}
                        
                        # 檢查玩家是否已提交
                        if role not in game_state['current_moves']:
                            game_state['current_moves'][role] = action_data
                            received_count += 1
                            print(f"玩家 {role} 提交: {action_data}")
                            if received_count == 3:
                                input_received.set() # 3 個都收到了，解除阻塞
                                
                    except Exception as e:
                        print(f"接收玩家 {role} 操作失敗: {e}")
                        game_state['game_active'] = False
                        input_received.set() # 發生錯誤，解除阻塞
                        
                # 啟動三個執行緒來接收輸入
                threads = []
                for role in player_roles: # 迭代 P1, P2, P3
                    t = threading.Thread(target=get_player_move, args=(role,), daemon=True)
                    threads.append(t)
                    t.start()
                
                # 等待直到 3 個輸入全部收到或發生錯誤
                input_received.wait() 

                if not game_state['game_active'] or received_count < 3:
                    print("遊戲提前結束或玩家中斷")
                    break
                    
                # 3. 判斷回合勝負並更新狀態
                round_winner = determine_round_winner(game_state['current_moves'], player_roles)
                game_state['total_wins'][round_winner] += 1
                game_state['round_result'] = {
                    'winner': round_winner,
                    'moves': game_state['current_moves']
                }
                print(f"[Round {game_state['round']}] 贏家: {round_winner}")
                
                # 4. 檢查總勝負
                final_winner = check_win(game_state)
                game_state['round'] += 1
                
                # 遊戲結束，廣播結果
                if final_winner:
                    game_state['game_active'] = False
                    final_state = {
                        'turn': 'END',
                        'winner': final_winner,
                        'total_wins': game_state['total_wins']
                    }
                    final_msg = json.dumps(final_state) + "\n"
                    for p in players_list:
                        p.sendall(final_msg.encode())
                    break
                
        except Exception as e:
            print(f"Server Error: {e}")
        finally:
            # 清理資源 (與 template.py 保持一致)
            for file_stream in player_files.values():
                try: file_stream.close()
                except: pass
            for conn in player_conns.values():
                try: conn.close()
                except: pass
            server.close()
            print("Server 關閉")
            
    except Exception as e:
        print(f"Server setup error: {e}")
        server.close()

# ============================================
# 遊戲客戶端 (Game Client) - GUI
# ============================================

class CardClientGUI:
    
    def __init__(self, master, ip, port, role, game_socket, sock_file):
        self.master = master
        master.title(f"卡牌遊戲 - {role}")
        self.role = role
        self.game_socket = game_socket
        self.sock_file = sock_file
        self.hand = []
        self.is_my_turn = False
        self.game_active = True
        self.selected_card = None
        self.selected_mode = 'MAX'
        
        # UI 元素 (狀態、分數、手牌、模式選擇)
        self.status_label = tk.Label(master, text="等待發牌...", font=('Helvetica', 14))
        self.status_label.grid(row=0, column=0, columnspan=5)
        self.score_label = tk.Label(master, text="總勝場: P1:0 P2:0 P3:0", font=('Helvetica', 12))
        self.score_label.grid(row=1, column=0, columnspan=5)
        
        # 手牌按鈕 (Card Buttons)
        self.card_buttons = []
        for i in range(3):
            btn = tk.Button(master, text=f"Card {i+1}", font=('Helvetica', 16), width=10, 
                            command=lambda i=i: self.select_card(i), state=tk.DISABLED)
            btn.grid(row=2, column=i+1, padx=5, pady=10)
            self.card_buttons.append(btn)
        
        # 模式選擇 (Max/Min)
        self.mode_var = tk.StringVar(master, 'MAX')
        self.max_radio = tk.Radiobutton(master, text="比大", variable=self.mode_var, value='MAX')
        self.min_radio = tk.Radiobutton(master, text="比小", variable=self.mode_var, value='MIN')
        self.max_radio.grid(row=3, column=1)
        self.min_radio.grid(row=3, column=3)
        
        # 提交按鈕
        self.submit_btn = tk.Button(master, text="出牌", command=self.make_move, state=tk.DISABLED)
        self.submit_btn.grid(row=4, column=2, pady=20)
        
        threading.Thread(target=self.receive_updates, daemon=True).start()

    def select_card(self, index):
        """選擇要出的牌"""
        self.selected_card = self.hand[index]
        # 視覺回饋
        for i, btn in enumerate(self.card_buttons):
            btn.config(relief=tk.RAISED)
            if i == index:
                btn.config(relief=tk.SUNKEN)
        self.submit_btn.config(state=tk.NORMAL)

    def make_move(self):
        """提交出牌和模式"""
        if self.selected_card is None:
            messagebox.showwarning("警告", "請先選擇一張牌！")
            return
            
        move_data = {
            'card': self.selected_card,
            'mode': self.mode_var.get()
        }
        
        try:
            # 發送動作指令
            self.game_socket.sendall((json.dumps(move_data) + "\n").encode('utf-8'))
            
            # 移除已出的牌
            self.hand.remove(self.selected_card)
            self.selected_card = None
            
            self.update_hand_display()
            self.is_my_turn = False
            self.status_label.config(text="已提交，等待對手...")
            self.disable_input()
            
        except Exception as e:
            messagebox.showerror("錯誤", f"發送操作失敗: {e}")
            self.game_active = False

    def update_hand_display(self):
        """更新手牌按鈕顯示"""
        for i in range(3):
            if i < len(self.hand):
                self.card_buttons[i].config(text=str(self.hand[i]), state=tk.NORMAL if self.is_my_turn else tk.DISABLED)
            else:
                self.card_buttons[i].config(text="USED", state=tk.DISABLED)

    def disable_input(self):
        self.submit_btn.config(state=tk.DISABLED)
        for btn in self.card_buttons:
            btn.config(state=tk.DISABLED)

    def enable_input(self):
        self.submit_btn.config(state=tk.DISABLED) # 必須先選牌
        self.update_hand_display()

    def receive_updates(self):
        """在單獨的執行緒中從 Server 接收狀態更新"""
        while self.game_active:
            try:
                line = self.sock_file.readline()
                if not line:
                    self.master.after(0, lambda: messagebox.showerror("錯誤", "伺服器已斷線"))
                    self.game_active = False
                    break
                
                data = json.loads(line.strip())
                
                if data.get('status') == 'START':
                    self.hand = data.get('hand', [])
                    self.update_hand_display()
                    self.status_label.config(text="發牌完成，等待回合開始...")
                    
                elif data.get('turn') == 'ALL':
                    self.is_my_turn = True
                    self.master.after(0, lambda: self.status_label.config(text=f"回合 {data['round']}：請選擇牌和模式！"))
                    self.master.after(0, self.enable_input)
                    self.master.after(0, lambda: self.score_label.config(text=f"總勝場: P1:{data['total_wins']['P1']} P2:{data['total_wins']['P2']} P3:{data['total_wins']['P3']}"))
                    
                elif data.get('turn') == 'END':
                    winner = data['winner']
                    msg = f"遊戲結束！請關閉遊戲視窗。總贏家是: {winner}" if winner != 'Draw' else "遊戲平局！"
                    self.master.after(0, lambda: messagebox.showinfo("結果", msg))
                    self.game_active = False
                    
            except Exception as e:
                # ... 處理錯誤 ...
                pass

def run_client(ip, port, role):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
    except Exception as e:
        print(f"連線失敗: {e}")
        return
    
    s.sendall((role + "\n").encode('utf-8'))
    sock_file = s.makefile('r', encoding='utf-8')
    
    root = tk.Tk()
    app = CardClientGUI(root, ip, port, role, s, sock_file)
    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python card_game_3p_gui.py [server <port>] | [client <ip> <port> <P1|P2|P3>]")
        exit()
        
    mode = sys.argv[1]
    if mode == 'server':
        # 為了簡化，直接使用一個固定埠號
        run_server(sys.argv[2] if len(sys.argv) > 2 else 9000)
    elif mode == 'client':
        if len(sys.argv) < 5:
            print("Usage: python card_game_3p_gui.py client <ip> <port> <role>")
        else:
            run_client(sys.argv[2], sys.argv[3], sys.argv[4])