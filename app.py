from flask import Flask, request, jsonify
import json, os, requests, binascii, threading, time, concurrent.futures
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import like_pb2, like_count_pb2, uid_generator_pb2
from google.protobuf.message import DecodeError
import logging
from queue import Queue
import signal
import sys
import urllib3
from google_play_scraper import app as google_play_app

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

flask_app = Flask(__name__)

ACCOUNTS_FILE = 'accounts.json'
TOKENS_FILE = 'tokens.json'
UPDATE_INTERVAL = 6 * 60 * 60

accounts_tokens = {}
tokens_lock = threading.Lock()
update_thread = None
running = True
is_updating = False

current_payload_bytes = None
current_server_url = "https://loginbp.ggpolarbear.com"
current_release_version = "OB52"
current_open_id = "4306245793de86da425a52caadf21eed"
current_access_token = "c69ae208fad72738b674b2847b50a3a1dfa25d1a19fae745fc76ac4a0e414c94"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def EnV(n):
    if n < 0: raise ValueError("non-negative only")
    o = []
    while True:
        b = n & 0x7F
        n >>= 7
        o.append(b | 0x80 if n else b)
        if not n: break
    return bytes(o)

def VFi(f, v):
    return EnV((f << 3) | 0) + EnV(v)

def LFi(f, v):
    b = v.encode() if isinstance(v, str) else v
    return EnV((f << 3) | 2) + EnV(len(b)) + b

def TerGeT(d):
    p = bytearray()
    for k, v in d.items():
        f = int(k)
        if isinstance(v, dict):
            p += LFi(f, TerGeT(v))
        elif isinstance(v, int):
            p += VFi(f, v)
        elif isinstance(v, (str, bytes)):
            p += LFi(f, v)
    return bytes(p)

def fetch_latest_data():
    global current_server_url, current_release_version, current_payload_bytes, current_open_id, current_access_token
    
    try:
        result = google_play_app('com.dts.freefireth', lang="fr", country='fr')
        version = result['version']
        r = requests.get(f'https://bdversion.ggbluefox.com/live/ver.php?version={version}&lang=ar&device=android&channel=android&appstore=googleplay&region=ME&whitelist_version=1.3.0&whitelist_sp_version=1.0.0&device_name=google%20G011A&device_CPU=ARMv7%20VFPv3%20NEON%20VMH&device_GPU=Adreno%20(TM)%20640&device_mem=1993', timeout=30).json()
        
        current_server_url = r['server_url']
        current_release_version = r['latest_release_version']
        
        fields = {
            3: "2025-11-26 01:51:28",
            4: "free fire",
            5: 1,
            7: version,
            8: "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)",
            9: "Handheld",
            10: "MTN/Spacetel",
            11: "WIFI",
            12: 1280,
            13: 720,
            14: "240",
            15: "x86-64 SSE3 SSE4.1 SSE4.2 AVX AVX2 | 2400 | 4",
            16: 3942,
            17: "Adreno (TM) 640",
            18: "OpenGL ES 3.2",
            19: "Google|625f716f-91a7-495b-9f16-08fe9d3c6533",
            20: "176.28.139.185",
            21: "ar",
            22: current_open_id,
            23: "4",
            24: "Handheld",
            25: "OnePlus A5010",
            29: current_access_token,
            30: 1,
            41: "MTN/Spacetel",
            42: "WIFI",
            57: "1ac4b80ecf0478a44203bf8fac6120f5",
            60: 46901,
            61: 32794,
            62: 2479,
            63: 900,
            64: 34727,
            65: 46901,
            66: 34727,
            67: 46901,
            70: 4,
            73: 1,
            74: "/data/app/com.dts.freefireth-fpXCSphIV6dKC7jL-WOyRA==/lib/arm",
            76: 1,
            77: "e62ab9354d8fb5fb081db338acb33491|/data/app/com.dts.freefireth-fpXCSphIV6dKC7jL-WOyRA==/base.apk",
            78: 6,
            79: 1,
            81: "32",
            83: "2019119026",
            85: 3,
            86: "OpenGLES2",
            87: 255,
            88: 4,
            92: 16190,
            93: "3rd_party",
            94: "KqsHT8W93GdcG3ZozENfFwVHtm7qq1eRUNaIDNgRobozIBtLOiYCc4Y6zvvpcICxzQF2sOE4cbytwLs4xZbRnpRMpmWRQKmeO5vcs8nQYBhwqH7K",
            95: 111207,
            97: 1,
            98: 1,
            99: "4",
            100: "4",
            102: "\u0013R\u0011FP\u000eY\u0003IQ\u000eF\t\u0000\u0011XC9_\u0000[Q\u000fh[V\na\u0007Wm\u000f\u0003f"
        }
        
        current_payload_bytes = TerGeT(fields)
        
        logger.info(f"تم جلب البيانات: Server={current_server_url}, Release={current_release_version}, Version={version}")
        
        return True
    except Exception as e:
        logger.error(f"خطأ في جلب البيانات: {e}")
        return False

def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
    return cipher_text.hex()

def token_maker(old_access_token, new_access_token, old_open_id, new_open_id, uid):
    try:
        if current_payload_bytes is None:
            if not fetch_latest_data():
                return None
        
        data = current_payload_bytes
        data = data.replace(old_open_id.encode(), new_open_id.encode())
        data = data.replace(old_access_token.encode(), new_access_token.encode())
        
        d = encrypt_api(data.hex())
        final_payload = bytes.fromhex(d)
        
        headers = {
            "Host": "loginbp.ggpolarbear.com",
            "X-Unity-Version": "2018.4.36f1",
            "Accept": "*/*",
            "Authorization": "Bearer",
            "ReleaseVersion": current_release_version,
            "X-GA": "v1 1",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(final_payload)),
            "User-Agent": "Free%20Fire/2019119624 CFNetwork/3826.500.111.2.2 Darwin/24.4.0",
            "Connection": "keep-alive"
        }
        
        URL = f"{current_server_url}/MajorLogin"
        RESPONSE = requests.post(URL, headers=headers, data=final_payload, verify=False, timeout=10)
        
        if RESPONSE.status_code == 200:
            if len(RESPONSE.text) < 10:
                return None
            BASE64_TOKEN = RESPONSE.text[RESPONSE.text.find("eyJhbGciOiJIUzI1NiIsInN2ciI6IjEiLCJ0eXAiOiJKV1QifQ"):-1]
            second_dot_index = BASE64_TOKEN.find(".", BASE64_TOKEN.find(".") + 1)
            BASE64_TOKEN = BASE64_TOKEN[:second_dot_index + 44]
            return BASE64_TOKEN
        else:
            return None
    except Exception as e:
        logger.error(f"خطأ في إنشاء التوكن: {e}")
        return None

def get_token_from_api(uid, password):
    try:
        url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
        }
        data = {
            "uid": f"{uid}",
            "password": f"{password}",
            "response_type": "token",
            "client_type": "2",
            "client_secret": "",
            "client_id": "100067",
        }
        
        response = requests.post(url, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            garena_data = response.json()
            
            if "access_token" not in garena_data or "open_id" not in garena_data:
                return None
            
            NEW_ACCESS_TOKEN = garena_data['access_token']
            NEW_OPEN_ID = garena_data['open_id']
            
            token = token_maker(current_access_token, NEW_ACCESS_TOKEN, current_open_id, NEW_OPEN_ID, uid)
            return token
        else:
            return None
            
    except Exception as e:
        logger.error(f"خطأ في جلب التوكن: {e}")
        return None

def load_accounts():
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                accounts_data = json.load(f)
                
                if isinstance(accounts_data, list):
                    accounts = {}
                    for account in accounts_data:
                        if isinstance(account, dict) and 'uid' in account and 'password' in account:
                            accounts[account['uid']] = account['password']
                    logger.info(f"تم تحميل {len(accounts)} حساب من {ACCOUNTS_FILE}")
                    return accounts
                elif isinstance(accounts_data, dict):
                    logger.info(f"تم تحميل {len(accounts_data)} حساب من {ACCOUNTS_FILE}")
                    return accounts_data
                else:
                    logger.warning(f"تنسيق ملف {ACCOUNTS_FILE} غير معروف")
                    return {}
        else:
            logger.warning(f"ملف {ACCOUNTS_FILE} غير موجود")
            return {}
    except Exception as e:
        logger.error(f"خطأ في تحميل الحسابات: {e}")
        return {}

def save_tokens_to_file():
    try:
        with tokens_lock:
            tokens_list = []
            for uid, token in accounts_tokens.items():
                tokens_list.append({
                    "uid": uid,
                    "token": token
                })
            
            with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tokens_list, f, indent=4, ensure_ascii=False)
        logger.info(f"تم حفظ {len(accounts_tokens)} توكن إلى {TOKENS_FILE}")
    except Exception as e:
        logger.error(f"خطأ في حفظ التوكنات: {e}")

def load_tokens_from_file():
    try:
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
                tokens_list = json.load(f)
                
                tokens_dict = {}
                for item in tokens_list:
                    if isinstance(item, dict) and 'uid' in item and 'token' in item:
                        tokens_dict[item['uid']] = item['token']
                
                logger.info(f"تم تحميل {len(tokens_dict)} توكن من {TOKENS_FILE}")
                return tokens_dict
        return {}
    except Exception as e:
        logger.error(f"خطأ في تحميل التوكنات: {e}")
        return {}

def fetch_token_thread(uid, password):
    token = get_token_from_api(uid, password)
    return uid, token

def update_all_tokens():
    global accounts_tokens, is_updating
    
    is_updating = True
    logger.info("بدء تحديث جميع التوكنات...")
    
    fetch_latest_data()
    
    accounts = load_accounts()
    if not accounts:
        logger.warning("لا توجد حسابات لتحديثها")
        is_updating = False
        return
    
    logger.info(f"جاري تحديث {len(accounts)} توكن...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        future_to_uid = {executor.submit(fetch_token_thread, uid, pwd): uid for uid, pwd in accounts.items()}
        
        successful = 0
        failed = 0
        
        for future in concurrent.futures.as_completed(future_to_uid):
            uid = future_to_uid[future]
            try:
                uid_result, token = future.result()
                if token:
                    with tokens_lock:
                        accounts_tokens[uid] = token
                    successful += 1
                    logger.debug(f"تم تحديث التوكن لـ {uid}")
                else:
                    failed += 1
                    logger.warning(f"فشل تحديث التوكن لـ {uid}")
            except Exception as e:
                failed += 1
                logger.error(f"خطأ في معالجة {uid}: {e}")
    
    save_tokens_to_file()
    is_updating = False
    logger.info(f"اكتمل التحديث: نجح {successful}, فشل {failed}")

def token_updater():
    while running:
        try:
            update_all_tokens()
            logger.info(f"الانتظار {UPDATE_INTERVAL//3600} ساعات للتحديث القادم...")
            
            for _ in range(UPDATE_INTERVAL):
                if not running:
                    break
                time.sleep(1)
        except Exception as e:
            logger.error(f"خطأ في دورة التحديث: {e}")
            time.sleep(60)

def start_token_updater():
    global update_thread, running, accounts_tokens
    
    accounts_tokens = load_tokens_from_file()
    fetch_latest_data()
    
    running = True
    update_thread = threading.Thread(target=token_updater, daemon=True)
    update_thread.start()
    logger.info("تم بدء خيط تحديث التوكنات")

def stop_token_updater():
    global running
    running = False
    if update_thread:
        update_thread.join(timeout=5)
    logger.info("تم إيقاف خيط تحديث التوكنات")

def encrypt_message(plaintext):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return binascii.hexlify(cipher.encrypt(pad(plaintext, AES.block_size))).decode()

def create_uid_proto(uid):
    pb = uid_generator_pb2.uid_generator()
    pb.saturn_ = int(uid)
    pb.garena = 1
    return pb.SerializeToString()

def create_like_proto(uid):
    pb = like_pb2.like()
    pb.uid = int(uid)
    return pb.SerializeToString()

def decode_protobuf(binary):
    try:
        pb = like_count_pb2.Info()
        pb.ParseFromString(binary)
        return pb
    except DecodeError:
        return None

def make_request(enc_uid, token):
    url = "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'Expect': "100-continue",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': current_release_version
    }
    try:
        res = requests.post(url, data=bytes.fromhex(enc_uid), headers=headers, verify=False, timeout=10)
        return decode_protobuf(res.content)
    except Exception as e:
        logger.error(f"خطأ في طلب المعلومات: {e}")
        return None

def send_like_thread(enc_uid, token, result_queue):
    url = "https://clientbp.ggblueshark.com/LikeProfile"
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'Expect': "100-continue",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': current_release_version
    }
    
    try:
        response = requests.post(url, data=bytes.fromhex(enc_uid), headers=headers, timeout=10)
        result_queue.put(response.status_code)
        return response.status_code
    except requests.RequestException as e:
        logger.error(f"خطأ في إرسال لايك: {e}")
        result_queue.put(None)
        return None

@flask_app.route('/like', methods=['GET'])
def like_handler():
    if is_updating:
        return jsonify({
            "status": "updating",
            "message": "جار تجديد التوكنات، يرجى المحاولة لاحقاً",
            "retry_after": 30
        }), 503
    
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "الرجاء إدخال UID"}), 400

    with tokens_lock:
        tokens = list(accounts_tokens.values())
    
    if not tokens:
        return jsonify({"error": "لا توجد توكنات متاحة، يرجى الانتظار حتى اكتمال التحديث"}), 401

    enc_uid = encrypt_message(create_uid_proto(uid))
    before = make_request(enc_uid, tokens[0])
    if not before:
        return jsonify({"error": "فشل في جلب معلومات اللاعب"}), 500

    before_data = json.loads(MessageToJson(before))
    likes_before = int(before_data.get("AccountInfo", {}).get("Likes", 0))
    nickname = before_data.get("AccountInfo", {}).get("PlayerNickname", "Unknown")

    enc_like_uid = encrypt_message(create_like_proto(uid))
    success_count = 0
    result_queue = Queue()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(send_like_thread, enc_like_uid, token, result_queue) for token in tokens]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                status = future.result()
                if status == 200:
                    success_count += 1
            except Exception as e:
                logger.error(f"خطأ في معالجة طلب إعجاب: {e}")

    after = make_request(enc_uid, tokens[0])
    likes_after = 0
    if after:
        after_data = json.loads(MessageToJson(after))
        likes_after = int(after_data.get("AccountInfo", {}).get("Likes", 0))

    return jsonify({
        "PlayerNickname": nickname,
        "UID": uid,
        "LikesBefore": likes_before,
        "LikesAfter": likes_after,
        "LikesGivenByAPI": likes_after - likes_before,
        "SuccessfulRequests": success_count,
        "TotalTokensUsed": len(tokens),
        "status": 1 if likes_after > likes_before else 2
    })

@flask_app.route('/reload_tokens', methods=['GET'])
def reload_tokens():
    global is_updating
    
    if is_updating:
        return jsonify({
            "status": "updating",
            "message": "جار تجديد التوكنات حالياً، يرجى الانتظار"
        }), 409
    
    threading.Thread(target=update_all_tokens, daemon=True).start()
    
    return jsonify({
        "status": "started",
        "message": "تم بدء تحديث التوكنات",
        "estimated_time": f"حوالي {len(load_accounts()) / 50} ثانية"
    })

@flask_app.route('/tokens_status', methods=['GET'])
def tokens_status():
    with tokens_lock:
        return jsonify({
            "total_tokens": len(accounts_tokens),
            "is_updating": is_updating,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "accounts_file_exists": os.path.exists(ACCOUNTS_FILE),
            "tokens_file_exists": os.path.exists(TOKENS_FILE),
            "current_release_version": current_release_version,
            "current_server_url": current_server_url
        })

@flask_app.route('/')
def home():
    with tokens_lock:
        token_count = len(accounts_tokens)
    
    return jsonify({
        "status": "online" if not is_updating else "updating",
        "message": "Like API is running ✅" if not is_updating else "جاري تحديث التوكنات ⏳",
        "active_tokens": token_count,
        "is_updating": is_updating,
        "update_interval_hours": UPDATE_INTERVAL // 3600,
        "release_version": current_release_version
    })

def signal_handler(sig, frame):
    logger.info("تلقي إشارة إيقاف...")
    stop_token_updater()
    sys.exit(0)
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 تشغيل خادم Free Fire API")
    print("="*50)
    print(f"📡 المنفذ: 7860")
    print(f"🌐 العنوان: http://0.0.0.0:7860")
    print("="*50 + "\n")
    
    flask_app.run(port=7860, host='0.0.0.0', debug=True)