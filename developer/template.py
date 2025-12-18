"""
這是一個用於創建新遊戲的模板文件，支持 2 人以上玩家及 GUI 介面。

使用說明：
1. 複製此文件並重命名為你的遊戲名稱（例如：my_game.py）。 
2. 實現以下函數：
   - check_win(): 檢查遊戲是否結束並返回勝者（P1, P2, P3... 或 Draw）。
   - print_board() / update_gui(): 打印遊戲狀態或更新圖形介面。
   - run_server(): 處理多人連線、同步狀態並判定勝負。
   - run_client(): 處理網路接收（需用 Threading 避免 GUI 卡死）與使用者操作。
3. 確保遊戲支持以下參數格式：
   - server: python game.py server <port>
   - client: python game.py client <ip> <port> <P1|P2|P3...> 
"""

import sys
import socket
import json
import threading
import time
import tkinter as tk  # 用於 GUI 實作
from tkinter import messagebox

# ============================================
# 1. 遊戲狀態管理 (GameState)
# ============================================

class GameState:
    def __init__(self, required_players):
        self.required_players = required_players
        self.players_info = {}  # 儲存角色與狀態
        self.board = []         # 核心遊戲數據（如棋盤或手牌）
        self.round = 1
        self.active = True
        self.winner = None

# ============================================
# 2. 遊戲服務器 (Game Server) - 支持多人
# ============================================

def run_server(port, player_count=2):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', int(port)))
        server.listen(player_count)
        print(f"[SERVER] 監聽中，等待 {player_count} 名玩家連線...")
        
        player_conns = {}
        player_files = {}
        
        # 建立多玩家連線
        for i in range(player_count):
            conn, addr = server.accept()
            role = f"P{i+1}"
            player_conns[role] = conn
            player_files[role] = conn.makefile('r', encoding='utf-8')
            print(f"[{role}] 已連線: {addr}")
            
            # 發送初始身分確認
            init_data = {"status": "START", "role": role, "hand": []} # 範例數據
            conn.sendall((json.dumps(init_data) + "\n").encode())

        # 遊戲主邏輯
        try:
            while True:
                # TODO: 實現廣播與同步邏輯
                # 使用 Thread 接收各玩家輸入以避免阻塞
                pass
        finally:
            server.close()
    except Exception as e:
        print(f"Server Error: {e}")

# ============================================
# 3. 遊戲客戶端 (Game Client) - 支持 GUI/CLI
# ============================================

class GameGUI:
    def __init__(self, sock, sock_file, role):
        self.root = tk.Tk()
        self.root.title(f"Game - {role}")
        self.sock = sock
        self.sock_file = sock_file
        self.role = role
        
        # 簡單 UI 範例
        self.label = tk.Label(self.root, text=f"你是 {role}，遊戲進行中...")
        self.label.pack(pady=20)
        
        # 重要：開啟獨立 Thread 接收資料，避免 GUI 卡死
        threading.Thread(target=self.receive_thread, daemon=True).start()
        self.root.mainloop()

    def receive_thread(self):
        while True:
            line = self.sock_file.readline()
            if not line: break
            data = json.loads(line.strip())
            # 更新介面
            self.root.after(0, lambda: self.label.config(text=f"回合: {data.get('round')}"))

def run_client(ip, port, role):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
        f = s.makefile('r', encoding='utf-8')
        
        # 可在此判斷要啟動 GUI 還是 CLI 
        GameGUI(s, f, role)
    except Exception as e:
        print(f"連線失敗: {e}")

# ============================================
# 4. 主程序入口
# ============================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python template.py [server <port> <count>] | [client <ip> <port> <role>]")
        exit()
    
    mode = sys.argv[1]
    if mode == 'server':
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 2
        run_server(sys.argv[2], count) 
    elif mode == 'client':
        run_client(sys.argv[2], sys.argv[3], sys.argv[4]) 