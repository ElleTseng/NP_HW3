import socket
import os
import sys
from common import send_json, recv_json, send_file, send_text

def check_environment():
    if sys.version_info < (3, 10):
        print("[錯誤] 本系統要求 Python 3.10 或以上版本。")
        sys.exit(1)
    else: print("Python版本符合")
    
    try:
        import tkinter
        print("tkinter已安裝")
    except ImportError:
        print("[錯誤] 找不到 tkinter 模組。")
        print("請執行 'sudo apt-get install python3-tk' 或其他指令安裝圖形套件。")
        sys.exit(1)

check_environment()

HOST = '140.113.17.12'
PORT = 16211
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))
send_text(client, "hi")

def show_game_reviews(game_name):
    send_json(client, {'cmd': 'get_reviews', 'name': game_name})
    res = recv_json(client)
    
    if not res or res.get('status') != 'ok':
        print(f"[錯誤] 無法獲取 {game_name} 的評論資訊")
        return

    reviews = res.get('reviews', [])
    print(f"\n=== 遊戲 [{game_name}] 的詳細評論 ===")
    if not reviews:
        print("目前尚無玩家留下評論。")
    else:
        for r in reviews:
            print(f"- {r['username']}: [ver.{r.get('version', '1')}][{r['rating']}分] {r['comment']}")
    print("====================================")

def main(user_id, username):
    print("=== 開發者後台 ===")
    while True:
        print("\n1. 查看遊戲列表\n2. 上架遊戲\n3. 更新遊戲\n4. 下架遊戲\n5. 離開")
        opt = input("選擇: ")
        
        if opt == '1': #查看遊戲列表
            send_json(client, {'cmd': 'list_games', 'user_id': user_id})
            res = recv_json(client)
            if res.get('status') == 'ok':
                games = res.get('games', {})
                if not games:
                    print("您尚未上傳任何遊戲")
                    continue
                print("\n=== 您上傳的遊戲 ===")
                game_names_list = list(games.keys())
                for i, name in enumerate(game_names_list):
                    info = games[name]
                    desc = info.get('desc')
                    ver = info.get('ver')
                    p_count = info.get('player_count') 

                    send_json(client, {'cmd': 'get_reviews', 'name': name})
                    rev_res = recv_json(client)
                    reviews = rev_res.get('reviews', [])
                    avg_rating = sum(r['rating'] for r in reviews) / len(reviews) if reviews else 0

                    print(f"{i+1}. [{name}] [ver. {ver}][{p_count}人遊戲][評分: {avg_rating:.1f}][{len(reviews)}則評論]")
                    print(f"   遊戲簡介: {desc}")

                while True:
                    try:
                        choice_num = int(input(f"\n請輸入要查看評論的遊戲編號 (1-{len(game_names_list)})，或輸入0返回: "))
                        if choice_num == 0:  break
                        
                        if 1 <= choice_num <= len(game_names_list):
                            selected_name = game_names_list[choice_num - 1] 
                            show_game_reviews(selected_name)
                            break
                        else:
                            print("編號無效，請重新輸入。")
                    except ValueError:
                        print("請輸入有效的數字。")
            else:
                print(f"Server 回應: {res.get('msg')}")
                
        elif opt == '2': #上架遊戲
            path = input("請輸入遊戲檔案名稱(需與本檔案在相同資料夾中)(如 tictactoe.py): ")
            if not os.path.exists(path):
                print("檔案不存在")
                continue

            name = input("請輸入遊戲名稱 (ID): ")
            if name == "": name = f"{path}default.py"

            desc = input("請輸入遊戲簡介: ")
            if desc == "": desc = "未提供簡介"

            while True: #版本
                try:
                    ver_input = int(input("請輸入遊戲版本號 (整數，例如 1): "))
                    if ver_input < 1:
                        raise ValueError
                    break
                except ValueError:
                    print("請輸入有效的正整數版本號")
               
            while True: #遊戲人數
                try:
                    p_count = int(input("請輸入遊戲人數 (最少2人): "))
                    if p_count < 2:
                        raise ValueError
                    break
                except ValueError:
                    print("請輸入有效的數字 (大於1)")
            
            send_json(client, {'cmd': 'upload', 'name': name, 'desc': desc,"user_id": user_id, "player_count": p_count, 'ver': ver_input})
            
            send_file(client, path)
            res = recv_json(client)
            print(f"Server 回應: {res['msg']}")

        elif opt == '3': #更新遊戲
            send_json(client, {'cmd': 'list_games', 'user_id': user_id})
            res = recv_json(client)
            if res.get('status') == 'ok':
                games = res.get('games', {})
                if not games:
                    print("您尚未上傳任何遊戲")
                    continue
                
                print("\n=== 您上傳的遊戲 ===")
                game_names_list = list(games.keys()) 
                for i, name in enumerate(game_names_list):
                    info = games[name]
                    desc = info.get('desc')
                    ver = info.get('ver')
                    p_count = info.get('player_count')
                    print(f"{i+1}. {name}: [ver. {ver}][{p_count}人遊戲] 遊戲簡介:{desc}")
            else:
                print(f"Server 回應: {res.get('msg')}")
                continue
            
            while True:
                try:
                    choice = int(input(f"請輸入要更新的遊戲編號 (1-{len(game_names_list)}): "))
                    if 1 <= choice <= len(game_names_list):
                        name = game_names_list[choice - 1] 
                        break
                    else:
                        print("編號無效，請重新輸入。")
                except ValueError:
                    print(f"請輸入有效的數字。")

            print(f"您選擇更新遊戲: {name}")
            path = input("請輸入新的遊戲檔案路徑 (例如 tictactoe.py): ")
            if not os.path.exists(path):
                print("檔案不存在")
                continue

            desc = input("請輸入新的遊戲簡介: ")
            if desc == "": desc = "未提供簡介"

            while True: #版本
                try:
                    ver_input = int(input("請輸入新的遊戲版本號 (整數): "))
                    if ver_input < 1:
                        raise ValueError
                    break
                except ValueError:
                    print("請輸入有效的正整數版本號")

            while True: #遊戲人數
                try:
                    p_count = int(input("請輸入新的遊戲人數 (例如 2): "))
                    if p_count < 2:
                        raise ValueError
                    break
                except ValueError:
                    print("請輸入有效的數字 (大於1)")

            send_json(client, {'cmd': 'update_game', 'name': name, 'desc': desc, 'user_id': user_id, "player_count": p_count, 'ver': ver_input})
            send_file(client, path)
            res = recv_json(client)
            print(f"Server 回應: {res.get('msg')}")
            res = recv_json(client)
            print(f"Server 回應: {res.get('msg')}")

        elif opt == '4': #下架遊戲
            send_json(client, {'cmd': 'list_games', 'user_id': user_id})
            res = recv_json(client)
            if res.get('status') == 'ok':
                games = res.get('games', {})
                if not games:
                    print("您尚未上傳任何遊戲")
                    continue

                print("\n=== 您上傳的遊戲 ===")
                game_names_list = list(games.keys()) 
                for i, name in enumerate(game_names_list):
                    info = games[name]
                    desc = info.get('desc')
                    ver = info.get('ver')
                    p_count = info.get('player_count')
                    print(f"{i+1}. {name}: [ver. {ver}][{p_count}人遊戲] 遊戲簡介:{desc}")
            else:
                print(f"Server 回應: {res.get('msg')}")
                continue

            while True:
                try:
                    choice = int(input(f"請輸入要下架的遊戲編號 (1-{len(game_names_list)}): "))
                    if 1 <= choice <= len(game_names_list):
                        name = game_names_list[choice - 1] 
                        break
                    else:
                        print("編號無效，請重新輸入。")
                except ValueError:
                    print(f"請輸入有效的數字。")

            send_json(client, {'cmd': 'delete_game', 'name': name, 'user_id': user_id})
            res = recv_json(client)
            print(f"Server 回應:  {res.get('msg')}")

        elif opt == '5': #離開
            send_json(client, {'cmd': 'logout', 'username': username})
            res = recv_json(client)
            if res.get('status') == 'ok':
                print("已登出")
            break
    client.close()

if __name__ == "__main__":
    username = input("Please enter your username:")
    password = input("Please enter your password:")
    user_type_input = 1

    send_json(client, {
    "collection": "User",
    "action": "create_or_login",
    "data": {
        "username": username,
        "password": password,
        "user_type": user_type_input
    }
    })
    
    reply = recv_json(client)
    if not reply or not reply.get("ok"):
        print("Login failed.")
        client.close()
        raise SystemExit
    data = reply["data"]
    user = data["user"]
    user_id = user["user_code"] 
    username = user["name"] 
    print(f"\nLogin successful. User Name: {username}\n")
    main(user_id, username)  
