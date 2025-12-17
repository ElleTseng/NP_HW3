import json
import struct
import os
FORMAT = 'utf-8'
MAX_LEN = 65536

def send_json(sock, data):
    try:
        json_bytes = json.dumps(data).encode(FORMAT)
        header = struct.pack('!I', len(json_bytes))
        sock.sendall(header + json_bytes)
    except Exception as e:
        print(f"[Error] Send JSON failed: {e}")

def recv_json(sock):
    try:
        header = sock.recv(4)
        if not header: return None
        length = struct.unpack('!I', header)[0]
        
        data = b''
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet: return None
            data += packet
        return json.loads(data.decode(FORMAT))
    except Exception as e:
        print(f"[Error] Recv JSON failed: {e}")
        return None

def send_file(sock, filepath):
    if not os.path.exists(filepath): 
        print(f"[Error] File not found: {filepath}")
        return False
    try:
        filesize = os.path.getsize(filepath)
        if filesize > 0xFFFFFFFF: #4 bytes header = 4GB
             raise ValueError(f"File size exceeds 4GB: {filesize} bytes")
        header = struct.pack('!I', filesize)
        sock.sendall(header)
        
        with open(filepath, 'rb') as f:
            while True:
                bytes_read = f.read(4096)
                if not bytes_read: break
                sock.sendall(bytes_read)
        return True
    except Exception as e:
        print(f"[Error] Send file failed: {e}")
        return False

def recv_file(sock, savepath):
    try:        
        dir_path = os.path.dirname(savepath)
        if not os.path.exists(dir_path): os.makedirs(dir_path)
        
        header = sock.recv(4)
        if not header or len(header) < 4:
            print(f"[ERROR] Failed to receive file header for {savepath}")
            return False
        filesize = struct.unpack('!I', header)[0]
        print(f"正在接收文件 ({filesize} bytes)...")
        
        received_len = 0
        last_progress = 0
        with open(savepath, 'wb') as newFile:
            while received_len < filesize:
                chunk = sock.recv(min(4096, filesize - received_len))
                if not chunk: 
                    print(f"[ERROR] Connection closed while receiving file, received {received_len}/{filesize} bytes")
                    break
                newFile.write(chunk)
                received_len += len(chunk)
                
                progress = int((received_len / filesize) * 100)
                if progress >= last_progress + 10:
                    print(f"下載進度: {progress}% ({received_len}/{filesize} bytes)")
                    last_progress = progress
        
        if received_len == filesize:
            print(f"文件接收完成: {savepath}")
            return True
        else:
            print(f"[ERROR] 文件不完整: 已接收 {received_len}/{filesize} bytes")
            return False
    except Exception as e:
        print(f"[ERROR] Recv file failed: {e}")
        return False

def recv_text(sock):
    try:
        header = sock.recv(4)
        if not header: return None
        length = struct.unpack("!I", header)[0]
        if length <= 0 or length > MAX_LEN: return None
        
        text = b''
        while len(text) < length:
            chunk = sock.recv(length - len(text))
            if not chunk: return None
            text += chunk
        if text is None: return None
        return text.decode(FORMAT) 
    except Exception as e:
        print(f"[Error] Recv text failed: {e}")
        return None

def send_text(sock, msg):
    try:
        data = msg.encode(FORMAT)
        length = len(data)
        if length <= 0 or length > MAX_LEN: 
            raise ValueError("Invalid payload length in send_text")
        header = struct.pack("!I", length)
        sock.sendall(header + data)
    except Exception as e:
        print(f"[Error] Send text failed: {e}")