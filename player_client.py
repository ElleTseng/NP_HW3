import socket
import os
import sys
import subprocess
import threading
import json
from common import send_json, recv_json, recv_file, send_text

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
LOCAL_GAMES_FILE = 'local_games.json'

def load_local_games(download_dir):
    file_path = os.path.join(download_dir, LOCAL_GAMES_FILE)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 加載本地遊戲記錄失敗: {e}")
            return {}
    return {}

def save_local_games(download_dir, local_games_db):
    file_path = os.path.join(download_dir, LOCAL_GAMES_FILE)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(local_games_db, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[ERROR] 保存本地遊戲記錄失敗: {e}")

# 每個玩家使用自己的下載目錄
def get_download_dir(username):
    """根據用戶名獲取下載目錄"""
    download_dir = os.path.join('player_downloads', username)
    if not os.path.exists(download_dir): os.makedirs(download_dir)
    return download_dir

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    client.connect((HOST, PORT))
    send_text(client, "hi")
except:
    print("連線失敗")

def show_reviews_and_rate(game_name):
    send_json(client, {'cmd': 'get_reviews', 'name': game_name})
    res = recv_json(client)
    print(f"\n=== {game_name} 的評論 ===")
    reviews = res.get('reviews', [])
    if not reviews: print("目前尚無評論。")
    else:
        for r in reviews:
            print(f"{r['username']}: [ver.{r.get('version', '1')}]{r['rating']}分 - {r['comment']}")
    
    action = input("\n是否要對此遊戲評分? (y/n): ")
    if action.lower() == 'y':
        try:
            rating = int(input("請輸入評分 (1-5): "))
            if not (1 <= rating <= 5):
                print("錯誤：評分必須在 1 到 5 之間。")
                return
            comment = input("請輸入評論 (最多50字): ")
            if len(comment) > 50:
                print("評論過長，已自動截斷。")
                comment = comment[:50]
                
            send_json(client, {
                'cmd': 'submit_review', 
                'name': game_name, 
                'rating': rating, 
                'comment': comment
            })
            result = recv_json(client)
            print(result.get('msg'))
        except ValueError:
            print("請輸入有效的數字。")
    
def wait_for_game_start(sock, download_dir):
    """在房間內等待 Server 通知遊戲開始"""
    print("正在等待其他玩家加入...")
    while True:
        res = recv_json(sock)
        if not res: 
            print("not receive any response from server")
            break
        
        if res.get('status') == 'game_start':
            print("\n!!! 遊戲開始 !!!")
            game_name = res['game']
            game_port = res['port']
            role = res['role'] 
            
            script_path = os.path.join(download_dir, f"{game_name}.py")
            print(f"正在啟動 {game_name} (Port {game_port})...")
            
            # 呼叫 subprocess 執行下載下來的 python 檔
            # 參數格式: python tictactoe.py client <IP> <PORT> <ROLE>
            subprocess.call([
                sys.executable, script_path, 
                'client', HOST, str(game_port), role
            ]) 
            
            print("遊戲結束，回到大廳。")
            break
        else:
            print(f"Sever回覆{res['status']}")

def main(username):
    DOWNLOAD_DIR = get_download_dir(username)
    local_games_db = load_local_games(DOWNLOAD_DIR)
    print("=== 遊戲大廳 ===")
    while True:
        print("\n1. 查看或評論遊戲\n2. 下載遊戲\n3. 瀏覽房間\n4. 建立房間 \n5. 加入房間\n6. 離開")
        choice = input("選擇(1~6): ")

        if choice == '1': #查看遊戲評論
            send_json(client, {'cmd': 'list_all_games'})
            res = recv_json(client)
            print("--- 商城列表 ---")
            if res and res.get('status') == 'ok' and 'games' in res:
                games = res['games']
                if games:
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

                        print(f"{i+1}.[{name}] [ver. {ver}][{p_count}人遊戲][評分: {avg_rating:.1f}][{len(reviews)}則評論]\n 遊戲簡介: {desc}")

                    while True:
                        try:
                            choice_num = int(input(f"\n請輸入要查看評論的遊戲編號 (1-{len(game_names_list)})或輸入0返回: "))
                            if choice_num == 0: break
                            if 1 <= choice_num <= len(game_names_list):
                                name = game_names_list[choice_num - 1] 
                                show_reviews_and_rate(name)
                                break
                            else:
                                print("編號無效，請重新輸入。")
                        except ValueError:
                            print("請輸入有效的數字。")
                else:
                    print("目前沒有可用的遊戲")
            else:
                print("獲取遊戲列表失敗")

        elif choice == '2': #下載遊戲
            send_json(client, {'cmd': 'list_all_games'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'games' in res:
                games = res['games']
                print("--- 商城列表 ---")
                if games:
                    game_names_list = list(games.keys())
                    for i, name in enumerate(game_names_list):
                        info = games[name]
                        desc = info.get('desc')
                        ver = info.get('ver')
                        p_count = info.get('player_count')
                        print(f"{i+1}. [{name}] [ver. {ver}][{p_count}人遊戲] 遊戲簡介: {desc}")

                    while True:
                        try:
                            choice_num = int(input(f"\n請輸入要下載的遊戲編號 (1-{len(game_names_list)}): "))
                            if 1 <= choice_num <= len(game_names_list):
                                name = game_names_list[choice_num - 1] 
                                break
                            else:
                                print("編號無效，請重新輸入。")
                        except ValueError:
                            print("請輸入有效的數字。")

                    send_json(client, {'cmd': 'download', 'name': name})
                    download_res = recv_json(client)
                    if download_res and download_res.get('status') == 'ok':
                        file_path = os.path.join(DOWNLOAD_DIR, f"{name}.py")
                        if recv_file(client, file_path):
                            print(f"下載完成！文件保存在: {file_path}")

                            #更新本地記錄
                            game_info = games[name]
                            local_games_db[name] = {
                                'ver': game_info.get('ver'),
                                'player_count': game_info.get('player_count'),
                                'desc': game_info.get('desc')
                            }
                            save_local_games(DOWNLOAD_DIR, local_games_db)
                        else:
                            print("下載失敗：文件接收錯誤")
                    else:
                        print(f"下載失敗: {download_res.get('msg', '未知錯誤') if download_res else '無回應'}")
                else:
                    print("目前沒有可用的遊戲")
            else:
                print("獲取遊戲列表失敗")

        elif choice == '3': #瀏覽房間
            send_json(client, {'cmd': 'list_rooms'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'rooms' in res:
                print("--- 房間列表 ---")
                if res['rooms']:
                    for rid, r_info in res['rooms'].items():
                        print(f"ID: {rid} | {r_info['display']}")
                else:
                    print("目前沒有可用的房間")
            else:
                print("獲取房間列表失敗")

        elif choice == '4': #建立房間
            send_json(client, {'cmd': 'list_all_games'})
            res = recv_json(client)
            if res and res.get('status') == 'ok' and 'games' in res:
                games = res['games']
                print("--- 商城列表 ---")
                if games:
                    game_names_list = list(games.keys())
                    for i, name in enumerate(game_names_list):
                        info = games[name]
                        desc = info.get('desc')
                        ver = info.get('ver')
                        p_count = info.get('player_count')
                        print(f"{i+1}. [{name}] [ver. {ver}][{p_count}人遊戲] 遊戲簡介: {desc}")
                    while True:
                        try:
                            choice_num = int(input(f"請輸入想玩的遊戲編號 (1-{len(game_names_list)}): "))
                            if 1 <= choice_num <= len(game_names_list):
                                game = game_names_list[choice_num - 1]
                                break
                            else:
                                print("編號無效，請重新輸入。")
                        except ValueError:
                            print("請輸入有效的數字。")
                else:
                    print("目前沒有可用的遊戲")
                    continue
            else:
                print("獲取遊戲列表失敗")
                continue
            
            game_info = games[game]
            server_ver = game_info.get('ver', 1)

            local_info = local_games_db.get(game)
            if local_info is None:
                print(f"尚未下載遊戲 [{game}]。 請先選擇 2.下載遊戲。")
                continue      
            local_ver = local_info.get('ver', 1)

            if local_ver != server_ver:
                print(f"您的遊戲版本為 {local_ver}，最新版本為 {server_ver}。 正在更新遊戲版本...\n")
                send_json(client, {'cmd': 'download', 'name': game})
                download_res = recv_json(client)
                if download_res and download_res.get('status') == 'ok':
                    file_path = os.path.join(DOWNLOAD_DIR, f"{game}.py")
                    if recv_file(client, file_path):
                        print("遊戲更新完成! 請再次選擇 4.建立房間。")
                        local_games_db[game] = {
                            'ver': server_ver,
                            'player_count': game_info.get('player_count'),
                            'desc': game_info.get('desc')
                        }
                        save_local_games(DOWNLOAD_DIR, local_games_db)
                        continue
                    else:
                        print("文件接收錯誤，更新失敗。")
                        continue
                else:
                    print(f"更新失敗: {download_res.get('msg')}")
                    continue

            send_json(client, {'cmd': 'create_room', 'game_name': game})
            res = recv_json(client)
            if res['status'] == 'ok':
                print(f"房間建立成功 (ID: {res['room_id']})")
                wait_for_game_start(client, DOWNLOAD_DIR) # 進入等待模式
            else:
                print(f"創建房間失敗: {res.get('msg', '未知錯誤')}")

        elif choice == '5': #加入房間
            send_json(client, {'cmd': 'list_rooms'})
            res = recv_json(client)

            rooms_data = {}
            if res and res.get('status') == 'ok' and 'rooms' in res:
                rooms_data = res['rooms']
                print("--- 房間列表 ---")
                if rooms_data:
                    for rid, r_info in rooms_data.items():
                        print(f"ID: {rid} | {r_info['display']}")
                else:
                    print("目前沒有可用的房間")
                    continue
            else:
                print("獲取房間列表失敗")

            selected_rid = None
            while True:
                rid = input("輸入房間 ID (輸入0取消): ")
                if rid == "0":
                    print("取消加入房間。")
                    break
                if rid in rooms_data:
                    selected_rid = rid
                    break
                else:
                    print(f"錯誤: 房間 ID [{rid}] 不存在或輸入無效。請重新輸入。")

            if selected_rid is None: continue
            room_info = rooms_data[selected_rid]
            game_to_join = room_info['game_name']

            local_info = local_games_db.get(game_to_join)
            if local_info is None:
                print(f"尚未下載遊戲 [{game_to_join}]。 請先選擇 2.下載遊戲。")
                continue  
            local_ver = local_info.get('ver', 1)

            send_json(client, {'cmd': 'list_all_games'})
            game_list_res = recv_json(client)
            games = game_list_res.get('games', {})
            game_info = games.get(game_to_join)
            if game_info is None:
                print(f"錯誤: 遊戲 [{game_to_join}] 已被下架。")
                continue
            server_ver = game_info.get('ver', 1)

            if local_ver != server_ver:
                print(f"您的遊戲版本為 {local_ver}，最新版本為 {server_ver}。 正在更新遊戲版本...\n")
                send_json(client, {'cmd': 'download', 'name': game_to_join})
                download_res = recv_json(client)
                if download_res and download_res.get('status') == 'ok':
                    file_path = os.path.join(DOWNLOAD_DIR, f"{game_to_join}.py")
                    if recv_file(client, file_path):
                        print("遊戲更新完成! 請再次選擇 5.加入房間。")
                        local_games_db[game_to_join] = {
                            'ver': server_ver,
                            'player_count': game_info.get('player_count'),
                            'desc': game_info.get('desc')
                        }
                        save_local_games(DOWNLOAD_DIR, local_games_db)
                        continue
                    else:
                        print("文件接收錯誤，更新失敗。")
                        continue
                else:
                    print(f"更新失敗: {download_res.get('msg')}")
                    continue

            send_json(client, {'cmd': 'join_room', 'room_id': rid})
            res = recv_json(client)
            if res and res.get('status') == 'ok':
                wait_for_game_start(client, DOWNLOAD_DIR)
            else:
                msg = res.get('msg', '未知錯誤')
                print(f"\n[加入失敗] Server回覆: {msg}")

        elif choice == '6': #離開
            print(f"正在登出用戶: {username}")
            send_json(client, {'cmd': 'logout', 'username': username})
            res = recv_json(client)
            print(f"Server回應: {res.get('msg')}")
            if res and res.get('status') == 'ok':
                print("已登出")
            else:
                print(f"登出失敗: {res.get('msg', '未知錯誤') if res else '無回應'}")
            break

    client.close()

if __name__ == "__main__":
    username = input("Please enter your username:")
    password = input("Please enter your password:")
    user_type_input = 0
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
    # 保存用戶名用於登出
    data = reply["data"]
    user = data["user"]
    username = user["name"]
    print(f"\nLogin successful. User Name: {username}\n")
    main(username)
