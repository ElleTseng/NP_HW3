# NP_HW3: Game Store System

## 啟動指南:
### 1. server端
   -step 1: 將common.py, server.py 和 DB.py 置於系計中的 Linux2  
   -step 2: 執行 server.py 和 DB.py  
   ```bash
   python server.py
   python DB.py
   ```
### 2. 開發者端 (上傳、更新、下架遊戲)
   -step 1: 將common.py, dev_client.py 及 開發中的遊戲 置於相同資料夾  
   -step 2: 執行 dev_client.py  
   ```bash
   python dev_client.py
   ```
### 3. 玩家端 (玩遊戲、評分)
   -step 1: 將common.py 及 player_client.py 置於相同資料夾  
   -step 2: 執行 player_client.py  
   ```bash
   python player_client.py
   ```
### 4. 備註:  
   -HOST(IP)、PORT若衝突，於各程式碼的最前端有相應變數可以修改  
## 其他相關檔案說明:
### 1. server端
  -all_info.db: 儲存使用者帳號及相關資訊  
  -games_db.json: 儲存商城中所有遊戲的中繼資料  
  -games_repo資料夾: 存放 Server 端已上架的遊戲
### 2. 開發者端
  -template.py: 遊戲開發模板  
  -ticatactoe.py: 雙人CLI遊戲範例  
  -ticatactoe_gui.py: 雙人GUI遊戲範例  
  -card_3p_gui.py: 多人GUI遊戲範例(3人)
### 3. 玩家端
  -player_downloads資料夾: 存放玩家本地下載的遊戲程式碼及相關資訊
### 4. 其他
  -common.py: JSON 與檔案傳輸協定
   
