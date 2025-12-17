import sys
import socket
import json
import time
import tkinter as tk
from tkinter import messagebox
import threading

def check_win(board):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] and board[a] != ' ':
            return board[a]
    if ' ' not in board: return 'Draw'
    return None

def run_server(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 允許 Port 重用，避免重開時卡住
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', int(port)))
    server.listen(2)
    print(f"[GAME SERVER] Listening on {port}")
    
    players = []
    player_files = []  
     
    # 等待兩個玩家連線
    print("等待玩家 1 連線...")
    conn1, addr1 = server.accept()
    players.append(conn1)
    player_files.append(conn1.makefile('r', encoding='utf-8'))
    print(f"Player 1 connected: {addr1}")

    print("等待玩家 2 連線...")
    conn2, addr2 = server.accept()
    players.append(conn2)
    player_files.append(conn2.makefile('r', encoding='utf-8'))
    print(f"Player 2 connected: {addr2}")
    
    board = [' '] * 9
    turn = 0 
    
    try:
        initial_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
        initial_msg = json.dumps(initial_state) + "\n"
        for p in players:
            try:
                p.sendall(initial_msg.encode())
            except:
                pass
        
        while True:
            current_player_idx = turn
            current_file = player_files[current_player_idx]
            print(f"等待 {'P1' if turn==0 else 'P2'} 輸入...")
            
            try:
                line = current_file.readline()
                #這裡去接受玩家的移動指令
                if not line:
                    print("玩家斷線")
                    break
                
                move_str = line.strip()
                print(f"收到輸入: {move_str}")
                
                if move_str.isdigit():
                    move = int(move_str)
                    if 0 <= move <= 8 and board[move] == ' ':
                        board[move] = 'O' if turn == 0 else 'X'
                        
                        # 3. 移動後檢查勝負
                        winner_symbol = check_win(board)
                        if winner_symbol:
                            # 將符號轉換為玩家名稱
                            if winner_symbol == 'O':
                                winner_name = 'P1'
                            elif winner_symbol == 'X':
                                winner_name = 'P2'
                            else:  
                                winner_name = 'Draw'
                            
                            # 廣播最後狀態和勝負結果
                            final_state = {'board': board, 'turn': 'END', 'winner': winner_name}
                            final_msg = json.dumps(final_state) + "\n"
                            for p in players:
                                try:
                                    p.sendall(final_msg.encode())
                                except:
                                    pass
                            print(f"遊戲結束: {winner_name} 獲勝")
                            break
                        
                        turn = 1 - turn
                        
                        updated_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
                        updated_msg = json.dumps(updated_state) + "\n"
                        for p in players:
                            try:
                                p.sendall(updated_msg.encode())
                            except:
                                pass
                    else:
                        print(f"無效移動: 位置 {move} 已被佔用或越界")
                        invalid_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
                        invalid_msg = json.dumps(invalid_state) + "\n"
                        for p in players:
                            try:
                                p.sendall(invalid_msg.encode())
                            except:
                                pass
                else:
                    print(f"收到非數字輸入: {move_str}")
                    invalid_state = {'board': board, 'turn': 'P1' if turn == 0 else 'P2'}
                    invalid_msg = json.dumps(invalid_state) + "\n"
                    for p in players:
                        try:
                            p.sendall(invalid_msg.encode())
                        except:
                            pass
            except ConnectionResetError:
                print("連線被重置")
                break

    except Exception as e:
        print(f"Server Error: {e}")
    finally:
        if 'player_files' in locals():
            for f in player_files:
                try:
                    f.close()
                except:
                    pass
        if 'players' in locals():
            for p in players:
                try:
                    p.close()
                except:
                    pass
        server.close()
        print("Server 關閉")

class TicTacToeClientGUI:
    def __init__(self, master, ip, port, role, game_socket, sock_file):
        self.master = master
        master.title(f"井字棋 - {role}")
        
        self.ip = ip
        self.port = port
        self.role = role
        self.symbol = 'O' if role == 'P1' else 'X'
        self.opponent_role = 'P2' if role == 'P1' else 'P1'
        self.game_socket = game_socket
        self.sock_file = sock_file
        
        self.board = [' '] * 9
        self.is_my_turn = False
        self.game_active = True

        self.status_label = tk.Label(master, text="等待對手...", font=('Helvetica', 14))
        self.status_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        self.buttons = []
        for i in range(9):
            btn = tk.Button(master, text=' ', font=('Helvetica', 20, 'bold'), width=5, height=2,
                            command=lambda i=i: self.make_move(i))
            btn.grid(row=(i//3) + 1, column=i%3, padx=5, pady=5)
            self.buttons.append(btn)
            
        # 啟動網路接收執行緒
        self.network_thread = threading.Thread(target=self.receive_updates, daemon=True)
        self.network_thread.start()

    def update_gui(self):
        """根據 self.board 更新 GUI 上的按鈕狀態"""
        for i in range(9):
            self.buttons[i].config(text=self.board[i])
            if self.board[i] != ' ' or not self.game_active or not self.is_my_turn:
                self.buttons[i].config(state=tk.DISABLED)
            else:
                self.buttons[i].config(state=tk.NORMAL)

    def update_status(self, message):
        """更新狀態欄訊息"""
        self.status_label.config(text=message)

    def make_move(self, index):
        """處理按鈕點擊，發送移動指令給 Server"""
        if self.is_my_turn and self.board[index] == ' ' and self.game_active:
            try:
                # 暫時禁用所有按鈕防止雙擊
                for btn in self.buttons:
                    btn.config(state=tk.DISABLED)
                    
                move = str(index)
                # 發送移動指令，注意要加換行符號以配合 Server 的 readline() 接收
                self.game_socket.sendall((move + "\n").encode('utf-8'))
                self.update_status(f"已發送移動 {index}，等待 {self.opponent_role}...")
                self.is_my_turn = False
                
            except Exception as e:
                messagebox.showerror("錯誤", f"發送操作失敗: {e}")
                self.game_active = False

    def receive_updates(self):
        """在單獨的執行緒中從 Server 接收遊戲狀態更新"""
        while self.game_active:
            try:
                line = self.sock_file.readline()
                if not line:
                    self.master.after(0, lambda: messagebox.showerror("錯誤", "伺服器已斷線"))
                    self.game_active = False
                    break
                
                data = json.loads(line.strip())
                
                # 更新棋盤狀態
                self.board = data.get('board', self.board)
                
                if 'winner' in data:
                    self.game_active = False
                    winner = data['winner']
                    if winner == self.role:
                        msg = "你贏了!遊戲結束，請關閉視窗。"
                    elif winner == 'Draw':
                        msg = "平局。遊戲結束，請關閉視窗。"
                    else:
                        msg = "你輸了。遊戲結束，請關閉視窗。"
                    
                    self.master.after(0, lambda: self.update_status(f"遊戲結束：{msg}"))
                    self.master.after(0, self.update_gui)
                    
                elif data.get('turn') == self.role:
                    self.is_my_turn = True
                    self.master.after(0, lambda: self.update_status(f"輪到你了 ({self.symbol})"))
                    self.master.after(0, self.update_gui)
                    
                else:
                    self.is_my_turn = False
                    self.master.after(0, lambda: self.update_status(f"等待 {self.opponent_role} 行動..."))
                    self.master.after(0, self.update_gui)
                    
            except Exception as e:
                if self.game_active:
                    self.master.after(0, lambda: messagebox.showerror("連線錯誤", f"遊戲接收錯誤: {e}"))
                self.game_active = False
                break
        
        try:
            self.game_socket.close()
        except:
            pass

def run_client(ip, port, role):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
    except Exception as e:
        print(f"連線失敗: {e}")
        return

    # 使用 makefile 避免 TCP 粘包問題，並將其傳遞給 GUI 類
    sock_file = s.makefile('r', encoding='utf-8')
    
    root = tk.Tk()
    app = TicTacToeClientGUI(root, ip, port, role, s, sock_file)
    root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tictactoe.py [server|client] ...")
        exit()
        
    mode = sys.argv[1]
    if mode == 'server':
        run_server(sys.argv[2])
    elif mode == 'client':
        run_client(sys.argv[2], sys.argv[3], sys.argv[4])
