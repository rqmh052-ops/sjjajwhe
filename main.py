#!/usr/bin/env python3
import sys
import time
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
import json
import os
from datetime import datetime, timedelta, timezone
import re
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import threading
import socket
import jwt
import random
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from cachetools import TTLCache
    print("✅ cachetools loaded")
except ImportError:
    print("❌ cachetools not installed")
    sys.exit(1)

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    print("✅ pycryptodome loaded")
except ImportError:
    print("❌ pycryptodome not installed")
    sys.exit(1)

try:
    from google.protobuf import descriptor as _descriptor
    from google.protobuf import descriptor_pool as _descriptor_pool
    from google.protobuf import symbol_database as _symbol_database
    from google.protobuf.internal import builder as _builder
    print("✅ protobuf loaded")
except ImportError:
    print("❌ protobuf not installed")
    sys.exit(1)

try:
    import lib2
    print("✅ lib2 loaded")
except ImportError as e:
    print(f"❌ Error loading lib2: {e}")
    sys.exit(1)

try:
    import my_pb2
    import output_pb2
    print("✅ my_pb2 and output_pb2 loaded")
except ImportError as e:
    print(f"❌ Error loading protobuf files: {e}")
    sys.exit(1)


async def send_message_with_retry(update, message, retries=3, delay=5):
    for attempt in range(retries):
        try:
            await update.message.reply_text(message, parse_mode='HTML')
            return
        except Exception as e:
            if 'Flood control exceeded' in str(e):
                print(f"Flood control exceeded, retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                raise e
    print("Failed to send message after multiple attempts.")

print("🔄 جاري تحميل البيانات الأولية...")
try:
    lib2.fetch_latest_data()
    print("✅ تم تحميل البيانات بنجاح")
except Exception as e:
    print(f"❌ فشل تحميل البيانات: {e}")
    print("⚠️ قد لا تعمل بعض الميزات بشكل صحيح")


TOKEN = "8411663176:AAGMVVfvQiFXR-dvyil5XYZsgRtvda44fck"
ADMIN_ID = 8287678319
JWT_TOKEN = None

FORCED_CHANNEL_ID = -1003886614381
last_token_update_time = 0
APPROVED_GROUPS_FILE = "approved_groups.json"
GROUP_EXPIRY_FILE = "group_expiry.json"
LIKE_STATUS_FILE = "like_status.json"
MAINTENANCE_STATUS_FILE = "maintenance_status.json"
BANNED_USERS_FILE = "banned_users.json"
ACCESS_TOKENS_FILE = "access_tokens.json"
TOKEN_STORE_FILE = "token_store.json"
VIDEO_FILE = "video_message.json"

EMOJI = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "like": "❤️",
    "player": "👤",
    "id": "🆔",
    "region": "🌐",
    "clock": "⏱️",
    "loading": "⏳",
    "celebrate": "🎉",
    "robot": "🤖",
    "handshake": "🤝",
    "photo": "📸",
    "activate": "🟢",
    "deactivate": "🔴",
    "rank_br": "🏅",
    "rank_cs": "🔫",
    "exp": "⚡",
    "calendar": "📅",
    "trophy": "🏆",
    "clan": "🏰",
    "clan_owner": "👑",
    "pet": "🐾",
    "credit_score": "🧾",
    "language": "🗣️",
    "signature": "💬",
    "account_info": "🌀",
    "game_version": "🧬",
    "lock": "🔒",
    "spam": "📨",
    "convert": "🔄",
    "ban": "🚫",
    "visit": "👀",
    "edit": "✏️",
    "key": "🔑",
    "password": "🔒",
    "text": "📝",
    "token": "🎫",
    "convert_token": "🔄",
    "login": "🔐",
    "invite": "🎮"
}

WAITING_FOR_METHOD, WAITING_FOR_ACCESS, WAITING_FOR_UID, WAITING_FOR_PASSWORD, WAITING_FOR_NEW_BIO = range(5)
WAITING_FOR_VIDEO = 6

bio_change_data = {}
token_store = {}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

connected_clients = {}
connected_clients_lock = threading.Lock()
account_queue = []
account_queue_lock = threading.Lock()
account_busy_for_commands = {}
account_busy_lock = threading.Lock()

def load_video():
    try:
        if os.path.exists(VIDEO_FILE):
            with open(VIDEO_FILE, 'r') as f:
                return json.load(f).get("video_id", None)
        return None
    except:
        return None

def save_video(video_id):
    with open(VIDEO_FILE, 'w') as f:
        json.dump({"video_id": video_id}, f)

def delete_video():
    if os.path.exists(VIDEO_FILE):
        os.remove(VIDEO_FILE)

video_message_id = load_video()

async def send_result_with_video(context, chat_id, text):
    try:
        if video_message_id:
            await context.bot.send_video(chat_id=chat_id, video=video_message_id, caption=text, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')
    except Exception as e:
        print(f"Error sending with video: {e}")
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')

def encode_varint(value):
    result = []
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)

def create_protobuf_packet(fields, field_number=1):
    packet = b''
    for field, value in fields.items():
        if isinstance(value, dict):
            sub_packet = create_protobuf_packet(value, field)
            tag = (field << 3) | 2
            packet += encode_varint(tag)
            packet += encode_varint(len(sub_packet))
            packet += sub_packet
        elif isinstance(value, int):
            tag = (field << 3) | 0
            packet += encode_varint(tag)
            packet += encode_varint(value)
        elif isinstance(value, str):
            tag = (field << 3) | 2
            packet += encode_varint(tag)
            packet += encode_varint(len(value))
            packet += value.encode()
        elif isinstance(value, bytes):
            tag = (field << 3) | 2
            packet += encode_varint(tag)
            packet += encode_varint(len(value))
            packet += value
    if field_number == 1:
        return packet
    return packet

def dec_to_hex(ask):
    ask_result = hex(ask)
    final_result = str(ask_result)[2:]
    if len(final_result) == 1:
        final_result = "0" + final_result
        return final_result
    else:
        return final_result

def encrypt_packet(plain_text, key, iv):
    plain_text = bytes.fromhex(plain_text)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
    return cipher_text.hex()

class FF_Client:
    def __init__(self, id, password):
        self.id = id
        self.password = password
        self.key = None
        self.iv = None
        self.connection_active = True
        self.CliEnts2 = None
        self.Get_FiNal_ToKen_0115()
    
    def is_available(self):
        return (hasattr(self, 'CliEnts2') and 
                self.CliEnts2 and 
                hasattr(self, 'key') and 
                self.key and
                hasattr(self, 'iv') and 
                self.iv and
                self.connection_active)
    
    def skwad_maker(self):
        fields = {
            1: 1,
            2: {
                2: "\u0001",
                3: 1,
                4: 1,
                5: "en",
                9: 1,
                11: 1,
                13: 1,
                14: {
                    2: 5756,
                    6: 11,
                    8: "1.109.5",
                    9: 3,
                    10: 2
                },
            }
        }
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def changes(self, num):
        fields = {
            1: 17,
            2: {
                1: 11371687918,
                2: 1,
                3: int(num),
                4: 62,
                5: "\u001a",
                8: 5,
                13: 329
            }
        }
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def invite_skwad(self, idplayer):
        fields = {
            1: 2,
            2: {
                1: int(idplayer),
                2: "ME",
                4: 1
            }
        }
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def leave_s(self):
        fields = {
            1: 7,
            2: {
                1: 11371687918
            }
        }
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def nmnmmmmn(self, data):
        if not self.key or not self.iv:
            return ""
        try:
            key = self.key if isinstance(self.key, bytes) else bytes.fromhex(self.key)
            iv = self.iv if isinstance(self.iv, bytes) else bytes.fromhex(self.iv)
            data = bytes.fromhex(data)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            cipher_text = cipher.encrypt(pad(data, AES.block_size))
            return cipher_text.hex()
        except Exception as e:
            print(f"Error in nmnmmmmn: {e}")
            return ""

    def execute_invite_command(self, player_id, squad_type):
        try:
            if not hasattr(self, 'CliEnts2') or not self.CliEnts2:
                print(f"Account {self.id}: Not connected, cannot execute invite")
                return False

            numsc = int(squad_type) - 1
            
            packetmaker = self.skwad_maker()
            self.CliEnts2.send(packetmaker)
            time.sleep(0.5)
            
            packetfinal = self.changes(int(numsc))
            self.CliEnts2.send(packetfinal)
            time.sleep(0.5)
            
            invite_packet = self.invite_skwad(player_id)
            self.CliEnts2.send(invite_packet)
            
            time.sleep(5)
            
            leave_packet = self.leave_s()
            self.CliEnts2.send(leave_packet)
            time.sleep(0.5)
            
            solo_packet = self.changes(1)
            self.CliEnts2.send(solo_packet)
            
            print(f"Account {self.id}: Invite sent to player {player_id} (squad: {squad_type})")
            return True
            
        except Exception as e:
            print(f"Account {self.id}: Error in execute_invite_command: {e}")
            return False

    def GeT_Key_Iv(self, serialized_data):
        try:
            import xKEys
            my_message = xKEys.MyMessage()
            my_message.ParseFromString(serialized_data)
            timestamp, key, iv = my_message.field21, my_message.field22, my_message.field23
            from google.protobuf.timestamp_pb2 import Timestamp
            timestamp_obj = Timestamp()
            timestamp_obj.FromNanoseconds(timestamp)
            timestamp_seconds = timestamp_obj.seconds
            timestamp_nanos = timestamp_obj.nanos
            combined_timestamp = timestamp_seconds * 1_000_000_000 + timestamp_nanos
            return combined_timestamp, key, iv
        except:
            return None, None, None

    def Guest_GeneRaTe(self, uid, password):
        try:
            self.url = "https://100067.connect.garena.com/oauth/guest/token/grant"
            self.headers = {"Host": "100067.connect.garena.com","User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)","Content-Type": "application/x-www-form-urlencoded","Accept-Encoding": "gzip, deflate, br","Connection": "close",}
            self.dataa = {"uid": f"{uid}","password": f"{password}","response_type": "token","client_type": "2","client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3","client_id": "100067",}
            self.response = requests.post(self.url, headers=self.headers, data=self.dataa).json()
            self.Access_ToKen, self.Access_Uid = self.response['access_token'], self.response['open_id']
            time.sleep(0.2)
            return self.ToKen_GeneRaTe(self.Access_ToKen, self.Access_Uid)
        except Exception as e: 
            print(f"Error in Guest_GeneRaTe: {e}")
            time.sleep(10)
            return self.Guest_GeneRaTe(uid, password)

    def GeT_LoGin_PorTs(self, JwT_ToKen, PayLoad):
        try:
            self.UrL = 'https://clientbp.ggwhitehawk.com/GetLoginData'
            self.HeadErs = {
                'Expect': '100-continue',
                'Authorization': f'Bearer {JwT_ToKen}',
                'X-Unity-Version': '2022.3.47f1',
                'X-GA': 'v1 1',
                'ReleaseVersion': 'OB53',
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
                'Host': 'clientbp.ggwhitehawk.com',
                'Connection': 'close',
                'Accept-Encoding': 'deflate, gzip',}        
            self.Res = requests.post(self.UrL, headers=self.HeadErs, data=PayLoad, verify=False)
            from byte import DeCode_PackEt
            self.BesTo_data = json.loads(DeCode_PackEt(self.Res.content.hex()))  
            address, address2 = self.BesTo_data['32']['data'], self.BesTo_data['14']['data'] 
            ip, ip2 = address[:len(address) - 6], address2[:len(address2) - 6]
            port, port2 = address[len(address) - 5:], address2[len(address2) - 5:]             
            return ip, port, ip2, port2          
        except:
            print("Failed To Get Ports")
            return None, None, None, None
        
    def ToKen_GeneRaTe(self, Access_ToKen, Access_Uid):
        try:
            self.UrL = "https://loginbp.ggpolarbear.com/MajorLogin"
            self.HeadErs = {
                'X-Unity-Version': '2022.3.47f1',
                'ReleaseVersion': 'OB53',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-GA': 'v1 1',
                'Content-Length': '928',
                'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
                'Host': 'loginbp.ggwhitehawk.com',
                'Connection': 'Keep-Alive',
                'Accept-Encoding': 'deflate, gzip'}   
            
            self.dT = bytes.fromhex('1a13323032352d31312d32362030313a35313a3238220966726565206669726528013a07312e3132332e314232416e64726f6964204f532039202f204150492d3238202850492f72656c2e636a772e32303232303531382e313134313333294a0848616e6468656c64520c4d544e2f537061636574656c5a045749464960800a68d00572033234307a2d7838362d3634205353453320535345342e3120535345342e32204156582041565832207c2032343030207c20348001e61e8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e329a012b476f6f676c657c36323566373136662d393161372d343935622d396631362d303866653964336336353333a2010e3137362e32382e3133392e313835aa01026172b201203433303632343537393364653836646134323561353263616164663231656564ba010134c2010848616e6468656c64ca010d4f6e65506c7573204135303130ea014063363961653230386661643732373338623637346232383437623530613361316466613235643161313966616537343566633736616334613065343134633934f00101ca020c4d544e2f537061636574656cd2020457494649ca03203161633462383065636630343738613434323033626638666163363132306635e003b5ee02e8039a8002f003af13f80384078004a78f028804b5ee029004a78f029804b5ee02b00404c80401d2043d2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f6c69622f61726de00401ea045f65363261623933353464386662356662303831646233333861636233333439317c2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f626173652e61706bf00406f804018a050233329a050a32303139313139303236a80503b205094f70656e474c455332b805ff01c00504e005be7eea05093372645f7061727479f205704b717348543857393347646347335a6f7a454e6646775648746d377171316552554e6149444e67526f626f7a4942744c4f695943633459367a767670634943787a514632734f453463627974774c7334785a62526e70524d706d5752514b6d654f35766373386e51594268777148374bf805e7e4068806019006019a060134a2060134b2062213521146500e590349510e460900115843395f005b510f685b560a6107576d0f0366')
            
            self.dT = self.dT.replace(b'2026-01-14 12:19:02', str(datetime.now())[:-7].encode())        
            self.dT = self.dT.replace(b'c69ae208fad72738b674b2847b50a3a1dfa25d1a19fae745fc76ac4a0e414c94', Access_ToKen.encode())
            self.dT = self.dT.replace(b'4306245793de86da425a52caadf21eed', Access_Uid.encode())
            
            from black9 import EnC_AEs
            hex_data = self.dT.hex()
            encoded_data = EnC_AEs(hex_data)
            self.PaYload = bytes.fromhex(encoded_data)
            
            self.ResPonse = requests.post(self.UrL, headers=self.HeadErs, data=self.PaYload, verify=False)        
            if self.ResPonse.status_code == 200 and len(self.ResPonse.text) > 10:
                from byte import DeCode_PackEt
                self.BesTo_data = json.loads(DeCode_PackEt(self.ResPonse.content.hex()))
                self.JwT_ToKen = self.BesTo_data['8']['data']           
                self.combined_timestamp, self.key, self.iv = self.GeT_Key_Iv(self.ResPonse.content)
                ip, port, ip2, port2 = self.GeT_LoGin_PorTs(self.JwT_ToKen, self.PaYload)            
                return self.JwT_ToKen, self.key, self.iv, self.combined_timestamp, ip, port, ip2, port2
            else:
                print(f"Error in ToKen_GeneRaTe, status: {self.ResPonse.status_code}")
                time.sleep(5)
                return self.ToKen_GeneRaTe(Access_ToKen, Access_Uid)
        except Exception as e:
            print(f"Error in ToKen_GeneRaTe: {e}")
            time.sleep(5)
            return self.ToKen_GeneRaTe(Access_ToKen, Access_Uid)
      
    def Get_FiNal_ToKen_0115(self):
        try:
            result = self.Guest_GeneRaTe(self.id, self.password)
            if not result:
                print("Failed to get tokens, retrying...")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            token, key, iv, Timestamp, ip, port, ip2, port2 = result
            
            if not all([ip, port, ip2, port2]):
                print("Failed to get ports, retrying...")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            self.JwT_ToKen = token
            self.key = key
            self.iv = iv
        
            try:
                import jwt
                self.AfTer_DeC_JwT = jwt.decode(token, options={"verify_signature": False})
                self.AccounT_Uid = self.AfTer_DeC_JwT.get('account_id')
                self.EncoDed_AccounT = hex(self.AccounT_Uid)[2:]
                from black9 import DecodE_HeX
                self.HeX_VaLue = DecodE_HeX(Timestamp)
                self.TimE_HEx = self.HeX_VaLue
                self.JwT_ToKen_ = token.encode().hex()
                print(f'Processing Uid : {self.AccounT_Uid}')
            except Exception as e:
                print(f"Error In Token : {e}")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            try:
                from black9 import EnC_PacKeT
                self.Header = hex(len(EnC_PacKeT(self.JwT_ToKen_, key, iv)) // 2)[2:]
                length = len(self.EncoDed_AccounT)
                self.__ = '00000000'
                if length == 9:
                    self.__ = '0000000'
                elif length == 8:
                    self.__ = '00000000'
                elif length == 10:
                    self.__ = '000000'
                elif length == 7:
                    self.__ = '000000000'
                else:
                    print('Unexpected length encountered')                
                self.Header = f'0115{self.__}{self.EncoDed_AccounT}{self.TimE_HEx}00000{self.Header}'
                self.FiNal_ToKen_0115 = self.Header + EnC_PacKeT(self.JwT_ToKen_, key, iv)
            except Exception as e:
                print(f"Error In Final Token : {e}")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            self.AutH_ToKen = self.FiNal_ToKen_0115
            self.Connect_SerVer(self.JwT_ToKen, self.AutH_ToKen, ip, port, key, iv, ip2, port2)        
            return self.AutH_ToKen, key, iv
            
        except Exception as e:
            print(f"Error in Get_FiNal_ToKen_0115: {e}")
            time.sleep(10)
            return self.Get_FiNal_ToKen_0115()

    def Connect_SerVer_OnLine(self, Token, tok, host, port, key, iv, host2, port2):
        try:
            self.AutH_ToKen_0115 = tok    
            self.CliEnts2 = socket.create_connection((host2, int(port2)))
            self.CliEnts2.send(bytes.fromhex(self.AutH_ToKen_0115))                  
        except:
            pass        
        while self.connection_active:
            try:
                self.DaTa2 = self.CliEnts2.recv(99999)
            except:
                time.sleep(1)
                                                            
    def Connect_SerVer(self, Token, tok, host, port, key, iv, host2, port2):
        self.AutH_ToKen_0115 = tok    
        self.CliEnts = socket.create_connection((host, int(port)))
        self.CliEnts.send(bytes.fromhex(self.AutH_ToKen_0115))  
        self.DaTa = self.CliEnts.recv(1024)          	        
        threading.Thread(target=self.Connect_SerVer_OnLine, args=(Token, tok, host, port, key, iv, host2, port2)).start()
        
        self.key = key
        self.iv = iv
        
        with connected_clients_lock:
            connected_clients[self.id] = self
            with account_queue_lock:
                if self.id not in account_queue:
                    account_queue.append(self.id)
            print(f"Account {self.id} registered, total accounts: {len(connected_clients)}")
        
        while self.connection_active:      
            try:
                self.DaTa = self.CliEnts.recv(1024)   
                if len(self.DaTa) == 0:
                    print(f"Connection lost for account {self.id}")
                    break
            except Exception as e:
                print(f"Error in Connect_SerVer: {e}")
                break

def get_next_available_account():
    with account_queue_lock:
        with account_busy_lock:
            for _ in range(len(account_queue)):
                if not account_queue:
                    return None
                
                account_id = account_queue.pop(0)
                
                if account_busy_for_commands.get(account_id, False):
                    account_queue.append(account_id)
                    continue
                
                with connected_clients_lock:
                    client = connected_clients.get(account_id)
                    if client and hasattr(client, 'is_available') and client.is_available():
                        account_queue.append(account_id)
                        return client
                    else:
                        continue
            
            return None

def mark_account_busy_for_commands(account_id):
    with account_busy_lock:
        account_busy_for_commands[account_id] = datetime.now()

def mark_account_free_for_commands(account_id):
    with account_busy_lock:
        if account_id in account_busy_for_commands:
            del account_busy_for_commands[account_id]

def load_accounts_from_file(filename="accs.json"):
    accounts = []
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, list):
                for account in data:
                    if isinstance(account, dict):
                        account_id = account.get('uid', '')
                        password = account.get('password', '')
                        if account_id:
                            accounts.append({
                                'id': str(account_id),
                                'password': password
                            })
            print(f"Loaded {len(accounts)} accounts from {filename}")
    except FileNotFoundError:
        print(f"File {filename} not found!")
    except Exception as e:
        print(f"Error reading file: {e}")
    return accounts

def start_account(account):
    try:
        print(f"Starting account: {account['id']}")
        FF_Client(account['id'], account['password'])
    except Exception as e:
        print(f"Error starting account {account['id']}: {e}")
        time.sleep(5)
        start_account(account)

def StarT_SerVer():
    ACCOUNTS = load_accounts_from_file()
    threads = []
    for account in ACCOUNTS:
        thread = threading.Thread(target=start_account, args=(account,))
        thread.daemon = True
        threads.append(thread)
        thread.start()
        time.sleep(1)
    time.sleep(3)
    for thread in threads:
        thread.join()

threading.Thread(target=StarT_SerVer, daemon=True).start()

async def convert_access_token_to_jwt(access_token):
    try:
        print(f"🔐 Converting Access Token to JWT: {access_token[:20]}...")
        
        inspect_url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        inspect_headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close"
        }
        
        inspect_response = requests.get(inspect_url, headers=inspect_headers, verify=False, timeout=30)
        
        if inspect_response.status_code != 200:
            print(f"❌ Failed to inspect Access Token: HTTP {inspect_response.status_code}")
            return None, "Invalid access token or token expired"
        
        token_data = inspect_response.json()
        
        if 'open_id' not in token_data or 'platform' not in token_data or 'uid' not in token_data:
            print("❌ Incomplete data in response")
            return None, "Incomplete token data"
        
        open_id = token_data["open_id"]
        platform_type = token_data["platform"]
        uid = str(token_data["uid"])
        
        print(f"✅ Access Token Data: UID={uid}, OpenID={open_id}, Platform={platform_type}")
        
        game_data = my_pb2.GameData()
        
        game_data.timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        game_data.game_name = "Free Fire"
        game_data.game_version = 1
        game_data.version_code = "1.122.1"
        game_data.os_info = "iOS 18.4"
        game_data.device_type = "Handheld"
        game_data.network_provider = "Verizon Wireless"
        game_data.connection_type = "WIFI"
        game_data.screen_width = 1170
        game_data.screen_height = 2532
        game_data.dpi = "460"
        game_data.cpu_info = "Apple A15 Bionic"
        game_data.total_ram = 6144
        game_data.gpu_name = "Apple GPU (5-core)"
        game_data.gpu_version = "Metal 3"
        game_data.user_id = uid
        game_data.ip_address = "172.190.111.97"
        game_data.language = "en"
        game_data.open_id = open_id
        game_data.access_token = access_token
        game_data.platform_type = platform_type
        game_data.field_99 = str(platform_type)
        game_data.field_100 = str(platform_type)
        
        KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
        IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
        
        serialized_data = game_data.SerializeToString()
        padded_data = pad(serialized_data, AES.block_size)
        cipher = AES.new(KEY, AES.MODE_CBC, IV)
        encrypted_data = cipher.encrypt(padded_data)
        
        url = "https://loginbp.ggpolarbear.com/MajorLogin"
        
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/octet-stream",
            "Expect": "100-continue",
            "X-GA": "v1 1",
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB53",
            "Content-Length": str(len(encrypted_data))
        }
        
        response = requests.post(url, data=encrypted_data, headers=headers, timeout=30, verify=False)
        
        if response.status_code == 200:
            jwt_msg = output_pb2.Garena_420()
            jwt_msg.ParseFromString(response.content)
            
            if jwt_msg.token:
                jwt_token = jwt_msg.token
                print(f"✅ Conversion successful! JWT Token: {jwt_token[:20]}...")
                
                if len(jwt_token) > 50 and "eyJ" in jwt_token:
                    return jwt_token, None
                else:
                    return None, "Invalid JWT format received"
            else:
                error_text = response.content.decode().strip()
                print(f"❌ Server error: {error_text}")
                
                error_messages = {
                    "BR_PLATFORM_INVALID_PLATFORM": "This account is registered on another platform",
                    "BR_GOP_TOKEN_AUTH_FAILED": "Invalid Access Token",
                    "BR_PLATFORM_INVALID_OPENID": "Invalid OpenID"
                }
                
                return None, error_messages.get(error_text, f"Server error: {error_text}")
        else:
            error_text = response.content.decode().strip() if response.content else "No error message"
            print(f"❌ Response failed: HTTP {response.status_code}, Error: {error_text}")
            return None, f"Server returned HTTP {response.status_code}"
            
    except requests.exceptions.Timeout:
        print("❌ Connection timeout")
        return None, "Connection timeout"
    except requests.exceptions.ConnectionError:
        print("❌ Connection error")
        return None, "Connection error"
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None, f"Unexpected error: {str(e)}"


async def convert_credentials_to_jwt(uid, password):
    try:
        print(f"🔐 Converting credentials: UID={uid}")
        
        headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close"
        }
        
        data = {
            "uid": str(uid),
            "password": str(password),
            "response_type": "token",
            "client_type": "2",
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_id": "100067"
        }
        
        response = requests.post(
            "https://100067.connect.garena.com/oauth/guest/token/grant",
            headers=headers, 
            data=data, 
            verify=False, 
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to get Access Token: HTTP {response.status_code}")
            return None, None, "Failed to get access token"
        
        data_response = response.json()
        
        if data_response.get("success") is True:
            resp = data_response.get("response", {})
            if resp.get("error") == "auth_error":
                return None, None, "Invalid UID or password"
        
        access_token = data_response.get("access_token")
        open_id = data_response.get("open_id")
        
        if not access_token or not open_id:
            print("❌ No Access Token or OpenID received")
            return None, None, "No access token or open_id received"
        
        print(f"✅ Access Token: {access_token[:20]}..., OpenID: {open_id}")
        
        jwt_token, error = await convert_access_token_to_jwt(access_token)
        
        if jwt_token:
            return access_token, jwt_token, None
        else:
            return access_token, None, error or "JWT conversion failed"
            
    except requests.exceptions.Timeout:
        print("❌ Connection timeout")
        return None, None, "Connection timeout"
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None, None, f"Unexpected error: {str(e)}"


async def check_ban_status_direct(uid):
    try:
        ban_url = f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}"
        ban_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "referer": "https://ff.garena.com/en/support/",
            "x-requested-with": "B6FksShzIgjfrYImLpTsadjS86sddhFH"
        }
        
        ban_response = requests.get(ban_url, headers=ban_headers, timeout=10)
        
        try:
            data = await get_account_info_local(uid)
            nickname = data.get('basicInfo', {}).get('nickname', '❌ Not Available')
            region = data.get('basicInfo', {}).get('region', '❌ Unknown')
        except:
            nickname = "❌ Not Available"
            region = "❌ Unknown"
        
        if ban_response.status_code == 200:
            data = ban_response.json().get("data", {})
            is_banned = data.get("is_banned", 0)
            period = data.get("period", 0)
            
            ban_status = "Banned 🚫" if is_banned == 1 else "Not Banned ✅"
            status_emoji = "🚫" if is_banned == 1 else "✅"
            
            return {
                "success": True,
                "name": nickname,
                "region": region,
                "is_banned": ban_status,
                "ban_period": period,
                "player_id": uid,
                "emoji": status_emoji
            }
        else:
            return {
                "success": False,
                "message": f"❌ Failed to check ban status. HTTP {ban_response.status_code}",
                "player_id": uid
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "❌ Connection timeout",
            "player_id": uid
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}",
            "player_id": uid
        }


def load_token_store():
    try:
        if os.path.exists(TOKEN_STORE_FILE):
            with open(TOKEN_STORE_FILE, 'r') as f:
                return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {}

def save_token_store(store):
    with open(TOKEN_STORE_FILE, 'w') as f:
        json.dump(store, f, indent=4, ensure_ascii=False)

def generate_token_id(token):
    import hashlib
    return hashlib.md5(token.encode()).hexdigest()[:8]

class TokenConverter:
    @staticmethod
    async def convert_access_token(access_token):
        try:
            print(f"🔄 Converting Access Token: {access_token[:20]}...")
            
            jwt_token, error_message = await convert_access_token_to_jwt(access_token)
            
            if jwt_token:
                return True, access_token, jwt_token, None
            else:
                return False, None, None, error_message or "Failed to convert access token to JWT"
                
        except Exception as e:
            print(f"❌ Error in convert_access_token: {e}")
            return False, None, None, f"Error: {str(e)}"
    
    @staticmethod
    async def convert_credentials(uid, password):
        try:
            print(f"🔄 Converting credentials: UID={uid}")
            
            access_token, jwt_token, error_message = await convert_credentials_to_jwt(uid, password)
            
            if access_token:
                if jwt_token:
                    return True, access_token, jwt_token, None
                else:
                    return True, access_token, None, error_message or "Got access token but JWT conversion failed"
            else:
                return False, None, None, error_message or "Failed to convert credentials"
                
        except Exception as e:
            print(f"❌ Error in convert_credentials: {e}")
            return False, None, None, f"Error: {str(e)}"

class BioManager:
    KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    
    @staticmethod
    def encrypt_api(plain_text):
        plain_text = bytes.fromhex(plain_text)
        cipher = AES.new(BioManager.KEY, AES.MODE_CBC, BioManager.IV)
        cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
        return cipher_text.hex()
    
    @staticmethod
    async def change_bio(uid=None, password=None, access_token=None, new_bio=""):
        try:
            jwt_token = None
            error_message = None
            
            if access_token:
                print(f"Using access token: {access_token[:20]}...")
                success, _, jwt_token, error_message = await TokenConverter.convert_access_token(access_token)
                if not success:
                    return False, error_message or "Failed to convert access token to JWT"
                
            elif uid and password:
                print(f"Using uid: {uid}, password: {password[:5]}...")
                success, _, jwt_token, error_message = await TokenConverter.convert_credentials(uid, password)
                if not success:
                    return False, error_message or "Failed to convert credentials to JWT"
                
            else:
                return False, "You must send either access token or uid and password"

            if not jwt_token:
                return False, error_message or "Failed to get JWT"

            success, message = await BioManager.update_bio_with_jwt(jwt_token, new_bio)
            
            if success:
                return True, message
            else:
                return False, message

        except Exception as e:
            print(f"Error in change_bio: {e}")
            return False, f"An error occurred: {str(e)}"
    
    @staticmethod
    async def update_bio_with_jwt(jwt_token, new_bio):
        try:
            game_data = my_pb2.GameData()
            
            game_data.user_id = "0"
            game_data.open_id = "0"
            game_data.access_token = jwt_token
            game_data.game_name = new_bio
            
            data_bytes = game_data.SerializeToString()
            padded_data = pad(data_bytes, AES.block_size)
            cipher = AES.new(BioManager.KEY, AES.MODE_CBC, BioManager.IV)
            encrypted_data = cipher.encrypt(padded_data)
            formatted_encrypted_data = ' '.join([f"{byte:02X}" for byte in encrypted_data])

            game_api_url = "https://clientbp.ggblueshark.com/UpdateSocialBasicInfo"
            data_bytes = bytes.fromhex(formatted_encrypted_data.replace(" ", ""))
            headers = {
                "Expect": "100-continue",
                "Authorization": f"Bearer {jwt_token}",
                "X-Unity-Version": "2018.4.11f1",
                "X-GA": "v1 1",
                "ReleaseVersion": "OB53",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
                "Host": "clientbp.ggblueshark.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip"
            }
            
            game_response = requests.post(game_api_url, headers=headers, data=data_bytes, timeout=10)
            
            if game_response.status_code == 200:
                return True, "Bio changed successfully"
            else:
                return False, f"Failed to update bio: {game_response.status_code}"
        except Exception as e:
            return False, f"Error updating bio: {str(e)}"

async def get_account_info_local(uid):
    try:
        if not uid or not uid.isdigit():
            return {
                "error": "Invalid request",
                "message": "Invalid 'uid' parameter. Please provide a valid numeric UID."
            }

        print(f"🔍 Attempting to fetch player info: UID={uid}")
        
        return_data = await lib2.GetAccountInformation(uid, "7", "ME", "/GetPlayerPersonalShow")
        
        if return_data and not return_data.get("error"):
            print(f"✅ Player found")
            return return_data
        else:
            return {
                "error": "Player not found",
                "message": f"Player with UID {uid} was not found."
            }
        
    except Exception as e:
        print(f"❌ Error fetching info: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": "Connection failed",
            "message": f"Unable to connect to Free Fire servers: {str(e)}",
            "error_type": type(e).__name__
        }

def convert_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
    except:
        return "Unknown"

def convert_timestamp_full(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return "Unknown"

def clean_signature(signature):
    return re.sub(r'\[[^\]]*\]', '', signature) if signature else ""

def load_like_status():
    try:
        if os.path.exists(LIKE_STATUS_FILE):
            with open(LIKE_STATUS_FILE, 'r') as f:
                return json.load(f).get("like_enabled", True)
        else:
            return True
    except (FileNotFoundError, json.JSONDecodeError):
        return True

def save_like_status(status):
    with open(LIKE_STATUS_FILE, 'w') as f:
        json.dump({"like_enabled": status}, f)

def load_maintenance_status():
    try:
        if os.path.exists(MAINTENANCE_STATUS_FILE):
            with open(MAINTENANCE_STATUS_FILE, 'r') as f:
                return json.load(f).get("maintenance_mode", False)
        else:
            return False
    except (FileNotFoundError, json.JSONDecodeError):
        return False

def save_maintenance_status(status):
    with open(MAINTENANCE_STATUS_FILE, 'w') as f:
        json.dump({"maintenance_mode": status}, f)

def load_banned_users():
    try:
        with open(BANNED_USERS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_banned_users(banned_users):
    with open(BANNED_USERS_FILE, 'w') as f:
        json.dump(banned_users, f, indent=4, ensure_ascii=False)

def load_access_tokens():
    try:
        if os.path.exists(ACCESS_TOKENS_FILE):
            with open(ACCESS_TOKENS_FILE, 'r') as f:
                return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {}

def save_access_tokens(access_tokens):
    with open(ACCESS_TOKENS_FILE, 'w') as f:
        json.dump(access_tokens, f, indent=4, ensure_ascii=False)

like_enabled = load_like_status()
maintenance_mode = load_maintenance_status()
token_store = load_token_store()

def load_approved_groups():
    try:
        with open(APPROVED_GROUPS_FILE, 'r') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_approved_groups(groups):
    with open(APPROVED_GROUPS_FILE, 'w') as f:
        json.dump(list(groups), f, indent=4)

def load_group_expiry():
    try:
        with open(GROUP_EXPIRY_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_group_expiry(expiry_data):
    with open(GROUP_EXPIRY_FILE, 'w') as f:
        json.dump(expiry_data, f, indent=4)

async def check_group_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    if chat_type != 'private':
        approved_groups = load_approved_groups()
        group_expiry = load_group_expiry()
        group_id_str = str(update.effective_chat.id)
        
        if group_id_str in approved_groups:
            return True
        
        if group_id_str in group_expiry:
            expiry_date_str = group_expiry[group_id_str]
            expiry_date = datetime.fromisoformat(expiry_date_str)
            if datetime.now(timezone.utc) < expiry_date:
                return True
            else:
                del group_expiry[group_id_str]
                save_group_expiry(group_expiry)
                
        error_msg = (
            f"{EMOJI['warning']} <b>Bot is not activated in this group.</b>\n"
            f"Please contact <a href='https://t.me/AlliFF_BOT'>AlliFF</a> to activate the bot.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return False
    return True

async def check_admin(update: Update):
    return str(update.effective_user.id) == str(ADMIN_ID)

async def check_ban_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id == str(ADMIN_ID):
        return False
        
    banned_users = load_banned_users()
    
    if user_id in banned_users:
        reason = banned_users[user_id]
        
        ban_message = (
            f"{EMOJI['ban']} <b>You are banned from using this bot.</b> {EMOJI['ban']}\n"
            f"{EMOJI['info']} <b>Reason:</b> <i>{reason}</i>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await send_message_with_retry(update, ban_message)
        return True
    return False

async def check_maintenance_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global maintenance_mode
    if maintenance_mode and str(update.effective_user.id) != str(ADMIN_ID):
        error_msg = (
            f"{EMOJI['warning']} <b>The bot is under maintenance.</b> {EMOJI['warning']}\n"
            f"{EMOJI['info']} It will be back soon.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return True
    return False

async def check_subscription(user_id, context):
    try:
        if not FORCED_CHANNEL_ID:
            print("Channel ID not configured")
            return True
        
        member = await context.bot.get_chat_member(chat_id=FORCED_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Failed to check subscription for user {user_id}: {e}")
        return True

async def send_subscription_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(text="Subscribe Here", url="https://t.me/AlliFF_YT_V3")
        ]])
        message = (
            f"{EMOJI['warning']} <b>Sorry, you must subscribe to the following channel to use the bot:</b>\n"
            f"<b><a href='https://t.me/AlliFF_YT_V3'>AlliFF Channel</a></b>\n"
            f"{EMOJI['info']} After subscribing, try using the command again.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await asyncio.sleep(0.5)
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        print(f"Error sending subscription message: {e}")
        try:
            simple_message = (
                f"⚠️ Sorry, you must subscribe to the following channel to use the bot:\n"
                f"AlliFF Channel: https://t.me/AlliFF_YT_V3\n"
                f"ℹ️ After subscribing, try using the command again.\n\n"
                f"Dev: @AlliFF_BOT\n"
                f"TEAM: D5M"
            )
            await update.message.reply_text(simple_message, disable_web_page_preview=True)
        except Exception as e2:
            print(f"Failed to send simple subscription message: {e2}")

async def can_use_command_in_private(update: Update):
    if update.effective_chat.type == 'private':
        if str(update.effective_user.id) != str(ADMIN_ID):
            await update.message.reply_text("🗿")
            return False
    return True


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 2:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/login ID PASSWORD</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/login 4388868414 mypassword123</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    uid = context.args[0]
    password = " ".join(context.args[1:])
    
    if not uid.isdigit():
        error_msg = (
            f"{EMOJI['error']} <b>Invalid ID.</b>\n"
            f"Please use numbers only for ID.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    processing_msg = await update.message.reply_text("<b>🔄 Converting credentials, please wait...</b>", parse_mode='HTML')
    
    try:
        success, access_token, jwt_token, error_message = await TokenConverter.convert_credentials(uid, password)
        
        if success:
            if jwt_token:
                caption = (
                    f"{EMOJI['success']} <b>✅ Credentials Conversion Successful!</b> {EMOJI['success']}\n\n"
                    
                    f"{EMOJI['id']} <b>Account ID:</b> <code>{uid}</code>\n"
                    f"{EMOJI['password']} <b>Password:</b> <code>{password[:10]}...</code>\n\n"
                    
                    f"{EMOJI['key']} <b>Access Token:</b>\n"
                    f"<code>{access_token}</code>\n\n"
                    
                    f"{EMOJI['token']} <b>JWT Token:</b>\n"
                    f"<code>{jwt_token}</code>\n\n"
                    
                    f"{EMOJI['info']} <b>How to copy:</b>\n"
                    f"1. Click and hold on the token text\n"
                    f"2. Select all text\n"
                    f"3. Copy to clipboard\n\n"
                    
                    f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                    f"<b>TEAM: D5M</b>"
                )
            else:
                caption = (
                    f"{EMOJI['warning']} <b>⚠️ Partial Conversion Successful!</b>\n\n"
                    
                    f"{EMOJI['id']} <b>Account ID:</b> <code>{uid}</code>\n"
                    f"{EMOJI['password']} <b>Password:</b> <code>{password[:10]}...</code>\n\n"
                    
                    f"{EMOJI['key']} <b>Access Token:</b>\n"
                    f"<code>{access_token}</code>\n\n"
                    
                    f"{EMOJI['error']} <b>Note:</b> JWT conversion failed: {error_message}\n\n"
                    
                    f"{EMOJI['info']} <b>How to copy:</b>\n"
                    f"1. Click and hold on the token text\n"
                    f"2. Select all text\n"
                    f"3. Copy to clipboard\n\n"
                    
                    f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                    f"<b>TEAM: D5M</b>"
                )
        else:
            caption = (
                f"{EMOJI['error']} <b>❌ Credentials Conversion Failed!</b>\n\n"
                f"{EMOJI['id']} <b>Account ID:</b> <code>{uid}</code>\n"
                f"{EMOJI['password']} <b>Password:</b> <code>{password[:10]}...</code>\n"
                f"{EMOJI['info']} <b>Error:</b> {error_message}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except Exception as e:
        print(f"Error in login command: {e}")
        caption = (
            f"{EMOJI['error']} <b>❌ Unexpected Error</b>\n\n"
            f"{EMOJI['info']} <b>Error:</b> {str(e)[:200]}\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)
    
async def access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/access ACCESS_TOKEN</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/access ff90c07eb9815af30a43b4a9f6019516e0e4c703b44092516d0defa4cef51f2a</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    access_token = " ".join(context.args)
    
    processing_msg = await update.message.reply_text("<b>🔄 Converting token, please wait...</b>", parse_mode='HTML')
    
    try:
        success, access_token_received, jwt_token, error_message = await TokenConverter.convert_access_token(access_token)
        
        if success:
            if jwt_token:
                caption = (
                    f"{EMOJI['success']} <b>✅ Token Conversion Successful!</b> {EMOJI['success']}\n\n"
                    
                    f"{EMOJI['key']} <b>Access Token:</b>\n"
                    f"<code>{access_token_received}</code>\n\n"
                    
                    f"{EMOJI['token']} <b>JWT Token:</b>\n"
                    f"<code>{jwt_token}</code>\n\n"
                    
                    f"{EMOJI['info']} <b>How to copy:</b>\n"
                    f"1. Click and hold on the token text\n"
                    f"2. Select all text\n"
                    f"3. Copy to clipboard\n\n"
                    
                    f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                    f"<b>TEAM: D5M</b>"
                )
            else:
                caption = (
                    f"{EMOJI['warning']} <b>Access Token Received</b>\n\n"
                    
                    f"{EMOJI['key']} <b>Access Token:</b>\n"
                    f"<code>{access_token_received}</code>\n\n"
                    
                    f"{EMOJI['error']} <b>Note:</b> JWT conversion failed: {error_message}\n\n"
                    
                    f"{EMOJI['info']} <b>How to copy:</b>\n"
                    f"1. Click and hold on the token text\n"
                    f"2. Select all text\n"
                    f"3. Copy to clipboard\n\n"
                    
                    f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                    f"<b>TEAM: D5M</b>"
                )
        else:
            caption = (
                f"{EMOJI['error']} <b>Token Conversion Failed!</b>\n\n"
                f"{EMOJI['key']} <b>Access Token:</b> <code>{access_token[:30]}...</code>\n"
                f"{EMOJI['info']} <b>Error:</b> {error_message}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except Exception as e:
        print(f"Error in access command: {e}")
        caption = (
            f"{EMOJI['error']} <b>Unexpected Error</b>\n\n"
            f"{EMOJI['info']} <b>Error:</b> {str(e)[:200]}\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)
    
async def copy_token_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("copy_token:"):
        parts = query.data.split(":")
        if len(parts) == 4:
            user_id, token_id, token_type = parts[1], parts[2], parts[3]
            
            token_key = f"{user_id}_{token_id}_{token_type}"
            if token_key in token_store:
                token = token_store[token_key]
                
                token_display_name = "Access Token" if token_type == "access" else "JWT Token"
                
                safe_token = token.replace("<", "&lt;").replace(">", "&gt;")
                
                reply_markup = InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"{EMOJI['success']} Close", callback_data="close_msg")
                ]])
                
                await query.edit_message_text(
                    text=f"{EMOJI['success']} <b>{token_display_name}</b>\n\n"
                         f"<code>{safe_token}</code>\n\n"
                         f"{EMOJI['info']} <b>Click and hold to select the token, then copy it.</b>\n\n"
                         f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                         f"<b>TEAM: D5M</b>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                await query.answer("Token expired or not found", show_alert=True)
        else:
            await query.answer("Invalid request", show_alert=True)

async def close_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "close_msg":
        await query.delete_message()

async def bio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            f"{EMOJI['info']} <b>This command must be used in private chat.</b>\n"
            f"Please go to private chat with the bot and use: <code>/bio</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if await check_maintenance_mode(update, context):
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['key']} Using Access Token", callback_data='access_method')],
        [InlineKeyboardButton(f"{EMOJI['password']} Using ID and Password", callback_data='idpass_method')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{EMOJI['edit']} <b>Change Free Fire Bio (Signature)</b>\n\n"
        f"{EMOJI['info']} <b>Choose login method:</b>\n\n"
        f"1. {EMOJI['key']} <b>Access Token</b> - If you have login token\n"
        f"2. {EMOJI['password']} <b>ID and Password</b> - Using account ID and password\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_METHOD

async def bio_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    if query.data == 'access_method':
        bio_change_data[user_id] = {'method': 'access'}
        
        await query.edit_message_text(
            f"{EMOJI['key']} <b>Access Token Method</b>\n\n"
            f"{EMOJI['info']} Now send me your <b>Access Token</b>.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return WAITING_FOR_ACCESS
    
    elif query.data == 'idpass_method':
        bio_change_data[user_id] = {'method': 'idpass'}
        
        await query.edit_message_text(
            f"{EMOJI['password']} <b>ID and Password Method</b>\n\n"
            f"{EMOJI['info']} Now send me your <b>Account ID.</b>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return WAITING_FOR_UID
        
async def receive_access_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    access_token = update.message.text.strip()
    
    bio_change_data[user_id]['access_token'] = access_token
    
    access_tokens = load_access_tokens()
    access_tokens[user_id] = access_token
    save_access_tokens(access_tokens)
    
    await update.message.reply_text(
        f"{EMOJI['success']} <b>Access Token saved successfully.</b>\n\n"
        f"{EMOJI['info']} Now send me the <b>new bio</b> you want to set.\n"
        f"{EMOJI['warning']} <i>Text can be in Arabic or English</i>\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    return WAITING_FOR_NEW_BIO

async def receive_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    uid = update.message.text.strip()
    
    if not uid.isdigit():
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Invalid ID.</b>\n"
            f"Please send numbers only.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return WAITING_FOR_UID
    
    bio_change_data[user_id]['uid'] = uid
    
    await update.message.reply_text(
        f"{EMOJI['success']} <b>Account ID saved.</b>\n\n"
        f"{EMOJI['info']} Now send me your <b>Password</b>.\n"
        f"{EMOJI['warning']} <i>It will be used to change bio only</i>\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    return WAITING_FOR_PASSWORD

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    password = update.message.text.strip()
    
    bio_change_data[user_id]['password'] = password
    
    await update.message.reply_text(
        f"{EMOJI['success']} <b>Password saved.</b>\n\n"
        f"{EMOJI['info']} Now send me the <b>new bio</b> you want to set.\n"
        f"{EMOJI['warning']} <i>Text can be in Arabic or English</i>\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    return WAITING_FOR_NEW_BIO

async def receive_new_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    new_bio = update.message.text.strip()
    
    if user_id not in bio_change_data:
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Session expired.</b>\n"
            f"Please start again with <code>/bio</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    user_data = bio_change_data[user_id]
    method = user_data.get('method')
    
    processing_msg = await update.message.reply_text("<b>🔄 Changing bio, please wait...</b>", parse_mode='HTML')
    
    try:
        if method == 'access':
            access_token = user_data.get('access_token')
            
            if not access_token:
                await processing_msg.delete()
                await send_result_with_video(context, update.effective_chat.id, f"{EMOJI['error']} <b>Access Token not found.</b>\nPlease try again.\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>")
                return ConversationHandler.END
            
            success, message = await BioManager.change_bio(
                access_token=access_token,
                new_bio=new_bio
            )
            
        elif method == 'idpass':
            uid = user_data.get('uid')
            password = user_data.get('password')
            
            if not uid or not password:
                await processing_msg.delete()
                await send_result_with_video(context, update.effective_chat.id, f"{EMOJI['error']} <b>Incomplete data.</b>\nPlease try again.\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>")
                return ConversationHandler.END
            
            success, message = await BioManager.change_bio(
                uid=uid,
                password=password,
                new_bio=new_bio
            )
        
        else:
            await processing_msg.delete()
            await send_result_with_video(context, update.effective_chat.id, f"{EMOJI['error']} <b>Unknown method.</b>\nPlease try again.\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>")
            return ConversationHandler.END
        
        await processing_msg.delete()
        
        if success:
            caption = (
                f"{EMOJI['success']} <b>Bio changed successfully!</b>\n\n"
                f"{EMOJI['text']} <b>New Bio:</b> <i>{new_bio}</i>\n"
                f"{EMOJI['info']} <b>Method:</b> {'Access Token' if method == 'access' else 'ID and Password'}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
        else:
            caption = (
                f"{EMOJI['error']} <b>Failed to change bio!</b>\n\n"
                f"{EMOJI['info']} <b>Error:</b> {message}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except requests.exceptions.Timeout:
        await processing_msg.delete()
        caption = (
            f"{EMOJI['error']} <b>Bio change timeout</b>\n\n"
            f"{EMOJI['info']} Server did not respond in time. Please try again later.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    except Exception as e:
        print(f"Error in receive_new_bio: {e}")
        await processing_msg.delete()
        caption = (
            f"{EMOJI['error']} <b>Unexpected error</b>\n\n"
            f"{EMOJI['info']} <b>Error:</b> {str(e)[:200]}\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    
    if user_id in bio_change_data:
        del bio_change_data[user_id]
    
    await send_result_with_video(context, update.effective_chat.id, caption)
    return ConversationHandler.END

async def cancel_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id in bio_change_data:
        del bio_change_data[user_id]
    
    await update.message.reply_text(
        f"{EMOJI['info']} <b>Bio change cancelled.</b>\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/info UID</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/info 6872869745</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    uid = context.args[0]
    
    if not uid.isdigit():
        error_msg = (
            f"{EMOJI['error']} <b>Invalid UID</b>\n"
            f"UID must contain only numbers\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    processing_msg = await update.message.reply_text("<b>📊 Fetching account information, please wait...</b>", parse_mode='HTML')

    try:
        data = await get_account_info_local(uid)
        
        if 'error' in data:
            error_msg = data.get('message', 'Unknown error')
            caption = (
                f"{EMOJI['error']} <b>Error fetching info</b>\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"❌ Error: {error_msg}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            await processing_msg.delete()
            await send_result_with_video(context, update.effective_chat.id, caption)
            return
        
        basic_info = data.get('basicInfo', {})
        clan_info = data.get('clanBasicInfo', {})
        captain_info = data.get('captainBasicInfo', {})
        social_info = data.get('socialInfo', {})
        credit_info = data.get('creditScoreInfo', {})
        pet_info = data.get('petInfo', {})
        
        signature = clean_signature(social_info.get('signature', ''))
        caption = (
            f"🌀 <b>Account Information:</b>\n"
            f"• 🏆 <b>Name:</b> {basic_info.get('nickname', 'Unknown')}\n"
            f"• 🆔 <b>ID:</b> <code>{uid}</code>\n"
            f"• 🌐 <b>Region:</b> {basic_info.get('region', 'Unknown')}\n"
            f"• ℹ️ <b>Level:</b> {basic_info.get('level', 'Unknown')}\n"
            f"• ⚡ <b>EXP:</b> {basic_info.get('exp', 'Unknown')}\n"
            f"• ❤️ <b>Likes:</b> {basic_info.get('liked', 'Unknown')}\n"
            f"• 🧬 <b>Game Version:</b> {basic_info.get('releaseVersion', 'Unknown')}\n"
            f"• 📅 <b>Created:</b> {convert_timestamp(basic_info.get('createAt', ''))}\n"
            f"• 🔓 <b>Last Login:</b> {convert_timestamp_full(basic_info.get('lastLoginAt', ''))}\n\n"
            
            f"ℹ️ <b>Rank Information:</b>\n"
            f"• 🏅 <b>BR Rank:</b> {basic_info.get('rank', 'Unknown')}\n"
            f"• 🔫 <b>CS Rank:</b> {basic_info.get('csRank', 'Unknown')}\n\n"
        )
        
        if clan_info.get('clanName'):
            caption += (
                f"🏰 <b>Clan Information:</b>\n"
                f"• 🏰 <b>Clan Name:</b> {clan_info.get('clanName', 'Unknown')}\n"
                f"• 🆔 <b>Clan ID:</b> {clan_info.get('clanId', 'Unknown')}\n"
                f"• ℹ️ <b>Clan Level:</b> {clan_info.get('clanLevel', 'Unknown')}\n"
                f"• ℹ️ <b>Members:</b> {clan_info.get('memberNum', 0)} / {clan_info.get('capacity', 0)}\n\n"
            )
            
            if captain_info.get('nickname'):
                caption += (
                    f"👑 <b>Clan Captain Info:</b>\n"
                    f"• 🏆 <b>Name:</b> {captain_info.get('nickname', 'Unknown')}\n"
                    f"• 🆔 <b>ID:</b> {captain_info.get('accountId', 'Unknown')}\n"
                    f"• ℹ️ <b>Level:</b> {captain_info.get('level', 'Unknown')}\n\n"
                )
        
        if pet_info.get('id'):
            caption += (
                f"🐾 <b>Pet Information:</b>\n"
                f"• ℹ️ <b>Pet Level:</b> {pet_info.get('level', 'Unknown')}\n"
                f"• ⚡ <b>Pet EXP:</b> {pet_info.get('exp', 'Unknown')}\n\n"
            )
        
        caption += (
            f"🗣️ <b>Other Information:</b>\n"
            f"• 💬 <b>Signature:</b> {signature[:100] + '...' if len(signature) > 100 else signature}\n"
            f"• 🧾 <b>Behavior:</b> {credit_info.get('creditScore', 'Unknown')}\n"
            f"• 🗣️ <b>Language:</b> {social_info.get('language', 'Unknown').replace('Language_', '')}\n\n"
            
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
            
    except Exception as e:
        print(f"Error in info command: {e}")
        caption = (
            f"{EMOJI['error']} <b>Unexpected error</b>\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"❌ Error: {str(e)[:200]}\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)

async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        await update.message.reply_text(f"{EMOJI['error']} <b>Not authorized.</b> This command is for main admin only.", parse_mode='HTML')
        return
        
    if len(context.args) < 1:
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Invalid format.</b>\n"
            f"Please use: <code>/ban_user [user_id] [reason]</code>\n\n"
            f"{EMOJI['info']} Example: <code>/ban_user 1234567890 annoying spam</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return

    user_id_to_ban = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Banned by main admin"
    
    if user_id_to_ban == str(ADMIN_ID):
        await update.message.reply_text(f"{EMOJI['warning']} <b>You cannot ban yourself.</b>", parse_mode='HTML')
        return

    banned_users = load_banned_users()
    
    if user_id_to_ban in banned_users:
        await update.message.reply_text(
            f"{EMOJI['info']} <b>User <code>{user_id_to_ban}</code> is already banned.</b>\n"
            f"{EMOJI['info']} <b>Current reason:</b> <i>{banned_users[user_id_to_ban]}</i>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return

    banned_users[user_id_to_ban] = reason
    save_banned_users(banned_users)
    
    await update.message.reply_text(
        f"{EMOJI['success']} <b>User banned successfully!</b> {EMOJI['ban']}\n"
        f"{EMOJI['id']} <b>User ID:</b> <code>{user_id_to_ban}</code>\n"
        f"{EMOJI['info']} <b>Reason:</b> <i>{reason}</i>\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    try:
        await context.bot.send_message(
            chat_id=user_id_to_ban, 
            text=f"{EMOJI['ban']} <b>You have been banned from using the bot.</b>\n{EMOJI['info']} <b>Reason:</b> <i>{reason}</i>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", 
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Failed to notify banned user {user_id_to_ban}: {e}")

async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        await update.message.reply_text(f"{EMOJI['error']} <b>Not authorized.</b> This command is for main admin only.", parse_mode='HTML')
        return
        
    if len(context.args) < 1:
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Invalid format.</b>\n"
            f"Please use: <code>/unban_user [user_id]</code>\n\n"
            f"{EMOJI['info']} Example: <code>/unban_user 1234567890</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return

    user_id_to_unban = context.args[0]
    banned_users = load_banned_users()

    if user_id_to_unban not in banned_users:
        await update.message.reply_text(
            f"{EMOJI['info']} <b>User <code>{user_id_to_unban}</code> is not banned.</b>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return

    del banned_users[user_id_to_unban]
    save_banned_users(banned_users)
    
    await update.message.reply_text(
        f"{EMOJI['success']} <b>User unbanned successfully!</b>\n"
        f"{EMOJI['id']} <b>User ID:</b> <code>{user_id_to_unban}</code>\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    try:
        await context.bot.send_message(
            chat_id=user_id_to_unban, 
            text=f"{EMOJI['success']} <b>Your ban has been lifted.</b> You can now use the bot again.\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", 
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Failed to notify unbanned user {user_id_to_unban}: {e}")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    
    if not await check_admin(update):
        return
        
    global maintenance_mode
    maintenance_mode = True
    save_maintenance_status(maintenance_mode)
    await update.message.reply_text(
        f"{EMOJI['warning']} <b>Maintenance mode activated.</b> {EMOJI['warning']}\n"
        f"{EMOJI['info']} Maintenance message will be sent to all active groups.\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    approved_groups = load_approved_groups()
    group_expiry_data = load_group_expiry()
    all_active_groups = set(approved_groups) | set(group_expiry_data.keys())
    
    maintenance_message = (
        f"{EMOJI['warning']} <b>The bot is under maintenance.</b> {EMOJI['warning']}\n"
        f"{EMOJI['info']} It will be fixed and back soon. Thank you for your patience.\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>"
    )
    
    for group_id in all_active_groups:
        try:
            await context.bot.send_message(chat_id=group_id, text=maintenance_message, parse_mode='HTML')
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Failed to send maintenance message to group {group_id}: {e}")

async def end_maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    
    if not await check_admin(update):
        return
        
    global maintenance_mode
    maintenance_mode = False
    save_maintenance_status(maintenance_mode)
    await update.message.reply_text(
        f"{EMOJI['success']} <b>Maintenance mode ended.</b> {EMOJI['success']}\n"
        f"{EMOJI['info']} Back online message will be sent to all active groups.\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    
    approved_groups = load_approved_groups()
    group_expiry_data = load_group_expiry()
    all_active_groups = set(approved_groups) | set(group_expiry_data.keys())
    
    end_maintenance_message = (
        f"{EMOJI['celebrate']} <b>The bot is back online!</b> {EMOJI['celebrate']}\n"
        f"{EMOJI['info']} Thank you for your patience, you can now use bot commands as usual.\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>"
    )
    
    for group_id in all_active_groups:
        try:
            await context.bot.send_message(chat_id=group_id, text=end_maintenance_message, parse_mode='HTML')
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Failed to send end maintenance message to group {group_id}: {e}")

async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not await check_admin(update):
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Not authorized to use this command.</b>\n"
            f"{EMOJI['info']} This command is for admin only.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return
        
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    
    if chat_type == 'private':
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
                f"{EMOJI['info']} Please use: <code>/activate [group_id]</code>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>",
                parse_mode='HTML'
            )
            return

        group_id = context.args[0]
        try:
            group_id = int(group_id)
        except ValueError:
            await update.message.reply_text(
                f"{EMOJI['error']} <b>Invalid group ID</b> {EMOJI['error']}\n\n"
                f"{EMOJI['info']} Group ID must be a number.\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            return
    else:
        group_id = update.effective_chat.id
        chat_administrators = await context.bot.get_chat_administrators(group_id)
        admin_ids = [admin.user.id for admin in chat_administrators]
        if user_id not in admin_ids and not await check_admin(update):
            error_msg = (
                f"{EMOJI['error']} <b>Not authorized to use this command.</b>\n"
                f"{EMOJI['info']} This command is for group admins only.\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            await update.message.reply_text(error_msg, parse_mode='HTML')
            return
    
    approved_groups = load_approved_groups()
    if str(group_id) in approved_groups:
        await update.message.reply_text(
            f"{EMOJI['warning']} <b>Bot is already activated in this group.</b>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        return
        
    approved_groups.add(str(group_id))
    save_approved_groups(approved_groups)
    
    await update.message.reply_text(
        f"{EMOJI['success']} <b>Bot activated successfully! (Permanent activation)</b> {EMOJI['success']}\n\n"
        f"{EMOJI['info']} You can now use bot commands in this group.\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    
    if chat_type == 'private':
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
                f"{EMOJI['info']} Please use: <code>/stop [group_id]</code>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>",
                parse_mode='HTML'
            )
            return

        group_id = context.args[0]
        try:
            group_id = int(group_id)
        except ValueError:
            await update.message.reply_text(
                f"{EMOJI['error']} <b>Invalid group ID</b> {EMOJI['error']}\n\n"
                f"{EMOJI['info']} Group ID must be a number.\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            return
    else:
        group_id = update.effective_chat.id
        chat_administrators = await context.bot.get_chat_administrators(group_id)
        admin_ids = [admin.user.id for admin in chat_administrators]
        if user_id not in admin_ids:
            error_msg = (
                f"Sorry this command is for bot admin only\n"
                f"To contact admin\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            await update.message.reply_text(error_msg, parse_mode='HTML')
            return
            
    approved_groups = load_approved_groups()
    group_expiry_data = load_group_expiry()
    group_id_str = str(group_id)

    if group_id_str in approved_groups:
        approved_groups.remove(group_id_str)
        save_approved_groups(approved_groups)
        
        await update.message.reply_text(
            f"{EMOJI['success']} <b>Bot deactivated successfully!</b> {EMOJI['success']}\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
    elif group_id_str in group_expiry_data:
        del group_expiry_data[group_id_str]
        save_group_expiry(group_expiry_data)
        
        await update.message.reply_text(
            f"{EMOJI['success']} <b>Bot (temporary) deactivated successfully!</b> {EMOJI['success']}\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"{EMOJI['warning']} <b>Bot is not activated in this group.</b>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return
    
async def disable_like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    
    global like_enabled
    if not await check_admin(update):
        await update.message.reply_text(f"{EMOJI['error']} <b>Not authorized.</b> This command is for admin only.\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
        return

    like_enabled = False
    save_like_status(like_enabled)
    await update.message.reply_text(
        f"{EMOJI['success']} <b>/like command disabled successfully.</b> {EMOJI['success']}\n"
        f"{EMOJI['info']} All like requests will now be rejected until you enable it again.\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )

async def enable_like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    
    global like_enabled
    if not await check_admin(update):
        await update.message.reply_text(f"{EMOJI['error']} <b>Not authorized.</b> This command is for admin only.\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
        return
        
    like_enabled = True
    save_like_status(like_enabled)
    await update.message.reply_text(
        f"{EMOJI['success']} <b>/like command enabled successfully!</b> {EMOJI['success']}\n"
        f"{EMOJI['info']} Users can now request likes again.\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )

async def leave_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    
    if not await check_admin(update):
        await update.message.reply_text(f"{EMOJI['error']} <b>Not authorized.</b> This command is for admin only.\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Invalid format.</b>\n"
            f"Please use: <code>/leave [group_id]</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return

    group_id = context.args[0]
    try:
        group_id = int(group_id)
    except ValueError:
        await update.message.reply_text(f"{EMOJI['error']} <b>Invalid group ID.</b>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
        return

    try:
        await context.bot.leave_chat(chat_id=group_id)
        await update.message.reply_text(f"{EMOJI['success']} <b>Left group successfully:</b> <code>{group_id}</code>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"{EMOJI['error']} <b>Failed to leave group:</b> {e}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')

async def sid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    
    if not await check_admin(update):
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Not authorized to use this command.</b>\n"
            f"{EMOJI['info']} This command is for main admin only.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return

    chat_type = update.effective_chat.type
    
    if chat_type == 'private':
        if len(context.args) < 2:
            await update.message.reply_text(
                f"{EMOJI['error']} <b>Invalid format.</b>\n"
                f"Please use: <code>/sid [group_id] [days]</code>\n\n"
                f"{EMOJI['info']} Example: <code>/sid -100123456789 7</code>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>",
                parse_mode='HTML'
            )
            return
        
        group_id_str = context.args[0]
        try:
            days = int(context.args[1])
            if days <= 0:
                await update.message.reply_text(f"{EMOJI['error']} <b>Number of days must be greater than zero.</b>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
                return
        except ValueError:
            await update.message.reply_text(f"{EMOJI['error']} <b>Invalid number of days.</b>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
            return
            
    else:
        group_id_str = str(update.effective_chat.id)
        
        if len(context.args) < 1:
            await update.message.reply_text(
                f"{EMOJI['error']} <b>Invalid format.</b>\n"
                f"Please use: <code>/sid [days]</code>\n\n"
                f"{EMOJI['info']} Example: <code>/sid 7</code> to activate bot for 7 days\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>",
                parse_mode='HTML'
            )
            return
            
        try:
            days = int(context.args[0])
            if days <= 0:
                await update.message.reply_text(f"{EMOJI['error']} <b>Number of days must be greater than zero.</b>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
                return
        except ValueError:
            await update.message.reply_text(f"{EMOJI['error']} <b>Invalid number of days.</b>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>", parse_mode='HTML')
            return

    group_expiry = load_group_expiry()
    expiry_date = datetime.now(timezone.utc) + timedelta(days=days)
    group_expiry[group_id_str] = expiry_date.isoformat()
    save_group_expiry(group_expiry)

    approved_groups = load_approved_groups()
    if group_id_str in approved_groups:
        approved_groups.remove(group_id_str)
        save_approved_groups(approved_groups)

    try:
        await asyncio.sleep(1)
        success_message = (
            f"{EMOJI['success']} <b>Bot activated in group for {days} days.</b>\n\n"
            f"{EMOJI['clock']} <b>Expires on:</b> <code>{expiry_date.strftime('%Y-%m-%d %H:%M:%S UTC')}</code>\n"
            f"{EMOJI['id']} <b>Group ID:</b> <code>{group_id_str}</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await send_message_with_retry(update, success_message)
    except Exception as e:
        print(f"Error sending sid success message: {e}")

async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not like_enabled:
        user_name = update.effective_user.mention_html()
        error_msg = f"{EMOJI['warning']} <b>Sorry {user_name}, no likes available at the moment. Please try again later.</b>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return

    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/like UID</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/like 6872869745</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    uid = context.args[0]
    
    processing_msg = await update.message.reply_text("<b>❤️ Sending likes, please wait...</b>", parse_mode='HTML')

    try:
        api_url = f"https://f比如我"
        response = requests.get(api_url, timeout=60, headers=HEADERS)
        response.raise_for_status()
        
        data = response.json()
        status = data.get('status')
        
        if status == 1:
            likes_given = data.get('LikesGivenByAPI', 0)
            likes_before = data.get('LikesbeforeCommand', 0)
            likes_after = data.get('LikesafterCommand', 0)
            nickname = data.get('PlayerNickname', 'Unknown')
            
            caption = (
                f"🎉 <b>Like sent successfully!</b> 🎉\n\n"
                f"👤 Name: <b>{nickname}</b>\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"❤️ Likes before: <code>{likes_before}</code>\n"
                f"❤️ Likes after: <code>{likes_after}</code>\n"
                f"✅ Likes sent: <code>{likes_given}</code>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
        elif status == 2:
            caption = (
                f"⚠️ <b>No likes sent!</b> ⚠️\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"📊 Status: <b>Already received likes recently</b>\n"
                f"💡 Tip: <i>Try again after 24 hours</i>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
        else:
            caption = (
                f"{EMOJI['error']} <b>Error sending likes</b>\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"📊 Status: <code>{status}</code>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except requests.exceptions.Timeout:
        caption = (
            f"{EMOJI['error']} <b>Like sending timeout</b>\n\n"
            f"{EMOJI['info']} Server did not respond in time. Please try again later.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    except requests.exceptions.HTTPError as err:
        caption = f"{EMOJI['error']} <b>Server connection error:</b> {err.response.status_code}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    except requests.exceptions.RequestException as e:
        caption = (
            f"{EMOJI['warning']} <b>Cannot send likes at the moment.</b>\n"
            f"{EMOJI['info']} <i>(API connection error)</i>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    except Exception as e:
        print(f"Error in like command: {e}")
        caption = f"{EMOJI['error']} <b>Unexpected error:</b> {str(e)}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)


async def friends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/friends UID</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/friends 760840390</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    uid = context.args[0]
    
    if not uid.isdigit():
        error_msg = (
            f"{EMOJI['error']} <b>Invalid UID</b>\n"
            f"UID must contain only numbers\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    processing_msg = await update.message.reply_text("<b>🤝 Sending friend requests, please wait...</b>", parse_mode='HTML')

    try:
        api_url = f"http://alliff-bot-spam-friends.hf.space/spam?uid={uid}"
        response = requests.get(api_url, timeout=60, headers=HEADERS)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 'success':
            successful_requests = data.get('successful_requests', 0)
            failed_requests = data.get('failed_requests', 0)
            total_tokens = data.get('total_tokens', 0)
            
            caption = (
                f"🤝 <b>Friend Requests Spam</b> 🤝\n\n"
                f"👤 Player ID: <code>{uid}</code>\n"
                f"✅ <b>Successful requests:</b> <code>{successful_requests}</code>\n"
                f"❌ <b>Failed requests:</b> <code>{failed_requests}</code>\n"
                f"🎫 <b>Tokens used:</b> <code>{total_tokens}</code>\n"
                f"\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
        else:
            caption = (
                f"{EMOJI['error']} <b>Friend request spam failed!</b>\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"❌ Error: {data.get('message', 'Unknown error')}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except requests.exceptions.Timeout:
        caption = (
            f"{EMOJI['error']} <b>Request timeout</b>\n\n"
            f"{EMOJI['info']} Server did not respond in time. Please try again later.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    except requests.exceptions.HTTPError as err:
        caption = f"{EMOJI['error']} <b>Server connection error:</b> {err.response.status_code}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    except Exception as e:
        print(f"Error in friends command: {e}")
        caption = f"{EMOJI['error']} <b>Unexpected error:</b> {str(e)}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)


async def spam_clan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/spam_clan CLAN_ID</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/spam_clan 3090773889</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    clan_id = context.args[0]
    
    if not clan_id.isdigit():
        error_msg = (
            f"{EMOJI['error']} <b>Invalid Clan ID</b>\n"
            f"Clan ID must contain only numbers\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    processing_msg = await update.message.reply_text("<b>🏰 Sending clan join requests, please wait...</b>", parse_mode='HTML')

    try:
        api_url = f"http://alliff-bot-spam-clan.hf.space/SpamClan?clan_id={clan_id}"
        response = requests.get(api_url, timeout=60, headers=HEADERS)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 'success':
            successful_requests = data.get('successful_requests', 0)
            failed_requests = data.get('failed_requests', 0)
            total_tokens = data.get('total_tokens', 0)
            
            caption = (
                f"🏰 <b>Clan Join Requests Spam</b> 🏰\n\n"
                f"🆔 Clan ID: <code>{clan_id}</code>\n"
                f"✅ <b>Successful requests:</b> <code>{successful_requests}</code>\n"
                f"❌ <b>Failed requests:</b> <code>{failed_requests}</code>\n"
                f"🎫 <b>Tokens used:</b> <code>{total_tokens}</code>\n"
                f"\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
        else:
            caption = (
                f"{EMOJI['error']} <b>Clan join request spam failed!</b>\n\n"
                f"🆔 Clan ID: <code>{clan_id}</code>\n"
                f"❌ Error: {data.get('message', 'Unknown error')}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except requests.exceptions.Timeout:
        caption = (
            f"{EMOJI['error']} <b>Request timeout</b>\n\n"
            f"{EMOJI['info']} Server did not respond in time. Please try again later.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    except requests.exceptions.HTTPError as err:
        caption = f"{EMOJI['error']} <b>Server connection error:</b> {err.response.status_code}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    except Exception as e:
        print(f"Error in spam_clan command: {e}")
        caption = f"{EMOJI['error']} <b>Unexpected error:</b> {str(e)}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)


async def visit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/visit UID</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/visit 760840390</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    uid = context.args[0]
    
    processing_msg = await update.message.reply_text("<b>👀 Sending visits, please wait...</b>", parse_mode='HTML')

    try:
        api_url = f"http://212.227.65.132:14689/visit?uid={uid}"
        response = requests.get(api_url, timeout=120, headers=HEADERS)
        response.raise_for_status()
        
        data = response.json()
        status = data.get('status')
        
        if status == 1:
            successful_visits = data.get('SuccessfulVisits', 0)
            total_requests = data.get('TotalRequests', 0)
            success_rate = data.get('SuccessRate', '0%')
            tokens_used = data.get('TokensUsed', 0)
            
            caption = (
                f"👀 <b>Visits sent successfully!</b> ✅\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"✅ Successful visits: <code>{successful_visits}</code>\n"
                f"📊 Total attempts: <code>{total_requests}</code>\n"
                f"📈 Success rate: <code>{success_rate}</code>\n"
                f"🎫 Tokens used: <code>{tokens_used}</code>\n"
                f"💡 Message: {data.get('message', 'Operation successful')}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
        else:
            message = data.get('message', 'Unknown failure')
            caption = (
                f"⚠️ <b>Failed to send visits!</b> ⚠️\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"📊 Status: <b>{message}</b>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except requests.exceptions.Timeout:
        caption = (
            f"{EMOJI['error']} <b>Visit sending timeout</b>\n\n"
            f"{EMOJI['info']} Server did not respond in time. Please try again later.\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    except requests.exceptions.HTTPError as err:
        caption = f"{EMOJI['error']} <b>Server connection error:</b> {err.response.status_code}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    except Exception as e:
        caption = f"{EMOJI['error']} <b>Unexpected error:</b> {str(e)}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)

async def baane_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b> {EMOJI['error']}\n\n"
            f"{EMOJI['info']} Please use:\n"
            f"<code>/baane UID</code>\n\n"
            f"{EMOJI['info']} Example:\n"
            f"<code>/baane 6872869745</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    uid = context.args[0]
    
    processing_msg = await update.message.reply_text("<b>🛡️ Checking ban status, please wait...</b>", parse_mode='HTML')

    try:
        result = await check_ban_status_direct(uid)
        
        if result.get('success'):
            name = result.get('name', 'Unknown')
            region = result.get('region', 'Unknown')
            ban_status = result.get('is_banned', 'Unknown')
            ban_period = result.get('ban_period', 0)
            status_emoji = result.get('emoji', '')
            
            caption = (
                f"🛡️ <b>Ban Check Result</b> 🛡️\n\n"
                f"👤 Name: <b>{name}</b>\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"🌐 Region: {region}\n"
                f"{status_emoji} Ban Status: <b>{ban_status}</b>\n"
                f"⏰ Ban Period: {ban_period} days\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
        else:
            error_msg = result.get('message', 'Ban check failed')
            caption = (
                f"{EMOJI['error']} <b>Ban check failed</b>\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"❌ Error: {error_msg}\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"<b>TEAM: D5M</b>"
            )
            
    except Exception as e:
        print(f"Error in baane command: {e}")
        caption = f"{EMOJI['error']} <b>Unexpected error:</b> {str(e)}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"
    
    await processing_msg.delete()
    await send_result_with_video(context, update.effective_chat.id, caption)

async def getid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == 'private':
        caption = (
            f"🆔 <b>ID Information</b> 🆔\n\n"
            f"👤 <b>Your ID:</b> <code>{user.id}</code>\n"
            f"💬 <b>This is a private chat</b>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    else:
        caption = (
            f"🆔 <b>ID Information</b> 🆔\n\n"
            f"👥 <b>Group ID:</b> <code>{chat.id}</code>\n"
            f"📛 <b>Group Name:</b> {chat.title}\n"
            f"👤 <b>Your ID:</b> <code>{user.id}</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
    
    await update.message.reply_text(caption, parse_mode='HTML')


async def invite_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, squad_size: str):
    if await check_ban_status(update, context): return
    if not await can_use_command_in_private(update): return
    if await check_maintenance_mode(update, context): return
    
    if not context.args or len(context.args) < 1:
        error_msg = (
            f"{EMOJI['error']} <b>Invalid format</b>\n"
            f"Please use: <code>/{squad_size} ID</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    target_id = context.args[0]
    
    if not target_id.isdigit():
        error_msg = (
            f"{EMOJI['error']} <b>Invalid ID</b>\n"
            f"ID must contain only numbers\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')
        return
    
    processing_msg = await update.message.reply_text(f"<b>🎮 Opening {squad_size} Player Squad, please wait...</b>", parse_mode='HTML')
    
    def process_invite():
        try:
            client = get_next_available_account()
            
            if not client:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(processing_msg.delete())
                loop.run_until_complete(send_result_with_video(context, update.effective_chat.id, 
                    f"{EMOJI['error']} <b>No accounts available. All accounts are busy. Please try again later.</b>\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"))
                loop.close()
                return
            
            account_id = client.id
            mark_account_busy_for_commands(account_id)
            
            try:
                success = client.execute_invite_command(target_id, squad_size)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(processing_msg.delete())
                
                if success:
                    caption = (
                        f"{EMOJI['success']} <b>Invite sent successfully!</b>\n\n"
                        f"👤 <b>Player ID:</b> <code>{target_id}</code>\n"
                        f"🎮 <b>Squad Size:</b> {squad_size} Players\n"
                        f"✅ <b>Status:</b> Invite sent\n\n"
                        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                        f"<b>TEAM: D5M</b>"
                    )
                else:
                    caption = (
                        f"{EMOJI['error']} <b>Failed to send invite!</b>\n\n"
                        f"👤 <b>Player ID:</b> <code>{target_id}</code>\n"
                        f"🎮 <b>Squad Size:</b> {squad_size} Players\n"
                        f"❌ <b>Status:</b> Failed\n\n"
                        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                        f"<b>TEAM: D5M</b>"
                    )
                
                loop.run_until_complete(send_result_with_video(context, update.effective_chat.id, caption))
                loop.close()
            finally:
                mark_account_free_for_commands(account_id)
        except Exception as e:
            print(f"Error in process_invite: {e}")
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(processing_msg.delete())
                loop.run_until_complete(send_result_with_video(context, update.effective_chat.id,
                    f"{EMOJI['error']} <b>Unexpected error:</b> {str(e)[:200]}\n\nDev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n<b>TEAM: D5M</b>"))
                loop.close()
            except:
                pass
    
    threading.Thread(target=process_invite, daemon=True).start()


async def set_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        await update.message.reply_text(f"{EMOJI['error']} <b>Not authorized.</b> This command is for main admin only.", parse_mode='HTML')
        return
    
    keyboard = [
        [InlineKeyboardButton("📹 Add Video", callback_data="add_video")],
        [InlineKeyboardButton("🗑️ Delete Video", callback_data="delete_video")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{EMOJI['info']} <b>Video Settings</b>\n\n"
        f"Current video: {'✅ Set' if video_message_id else '❌ Not set'}\n\n"
        f"Choose an option:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return WAITING_FOR_VIDEO

async def video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_video":
        await query.edit_message_text(
            f"{EMOJI['info']} <b>Send me the video you want to use.</b>\n\n"
            f"Please send a video file (as a message).\n"
            f"Type <code>/cancel</code> to cancel.",
            parse_mode='HTML'
        )
        return WAITING_FOR_VIDEO
    
    elif query.data == "delete_video":
        global video_message_id
        video_message_id = None
        delete_video()
        await query.edit_message_text(
            f"{EMOJI['success']} <b>Video deleted successfully!</b>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
        return ConversationHandler.END

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global video_message_id
    
    if update.message.video:
        video_id = update.message.video.file_id
        video_message_id = video_id
        save_video(video_id)
        
        await update.message.reply_text(
            f"{EMOJI['success']} <b>Video saved successfully!</b>\n\n"
            f"Video ID: <code>{video_id}</code>\n\n"
            f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"<b>TEAM: D5M</b>",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"{EMOJI['error']} <b>Please send a valid video file.</b>\n\n"
            f"Send me the video you want to use.\n"
            f"Type <code>/cancel</code> to cancel.",
            parse_mode='HTML'
        )
        return WAITING_FOR_VIDEO
    
    return ConversationHandler.END

async def cancel_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{EMOJI['info']} <b>Video setup cancelled.</b>\n\n"
        f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
        f"<b>TEAM: D5M</b>",
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban_status(update, context): return
    if update.effective_chat.type == 'private':
        if str(update.effective_user.id) != str(ADMIN_ID):
            await update.message.reply_text("🗿")
            return
        
    user = update.effective_user
    chat = update.effective_chat
    chat_type = chat.type
    
    if chat_type == 'private':
        caption = (
            f"╔═══════════════════════╗\n"
            f"║      🤖 BOT MENU      ║\n"
            f"╚═══════════════════════╝\n\n"
            
            f"✨ Welcome {user.mention_html()}! ✨\n\n"
            
            f"╔═══════════════════════╗\n"
            f"║  📋 PUBLIC COMMANDS   ║\n"
            f"╚═══════════════════════╝\n\n"
            
            f"• {EMOJI['invite']} <b>2 Player Squad:</b> <code>/2 ID</code>\n"
            f"• {EMOJI['invite']} <b>3 Player Squad:</b> <code>/3 ID</code>\n"
            f"• {EMOJI['invite']} <b>4 Player Squad:</b> <code>/4 ID</code>\n"
            f"• {EMOJI['invite']} <b>5 Player Squad:</b> <code>/5 ID</code>\n"
            f"• {EMOJI['invite']} <b>6 Player Squad:</b> <code>/6 ID</code>\n\n"                                    
            f"• {EMOJI['player']} <b>Get Info:</b> <code>/info UID</code>\n"
            f"• {EMOJI['like']} <b>Send Likes:</b> <code>/like UID</code>\n"
            f"• {EMOJI['handshake']} <b>Friend Spam:</b> <code>/friends UID</code>\n"
            f"• {EMOJI['clan']} <b>Clan Spam:</b> <code>/spam_clan CLAN_ID</code>\n"
            f"• {EMOJI['visit']} <b>Send Visits:</b> <code>/visit UID</code>\n"
            f"• {EMOJI['deactivate']} <b>Check Ban:</b> <code>/baane UID</code>\n"
            f"• {EMOJI['edit']} <b>Change Bio:</b> <code>/bio</code> (in private)\n"
            f"• {EMOJI['login']} <b>Convert Login:</b> <code>/login ID PASSWORD</code>\n"
            f"• {EMOJI['key']} <b>Convert Token:</b> <code>/access ACCESS_TOKEN</code>\n"
            f"• {EMOJI['id']} <b>Get ID:</b> <code>/getid</code>\n\n"
        )
        
        if await check_admin(update):
            caption += (
                f"╔═══════════════════════╗\n"
                f"║   🔑 ADMIN COMMANDS   ║\n"
                f"╚═══════════════════════╝\n\n"
                
                f"• {EMOJI['activate']} <b>Activate Bot:</b> <code>/activate [group_id]</code>\n"
                f"• {EMOJI['deactivate']} <b>Deactivate Bot:</b> <code>/stop [group_id]</code>\n"
                f"• {EMOJI['deactivate']} <b>Disable Likes:</b> <code>/disable_like</code>\n"
                f"• {EMOJI['activate']} <b>Enable Likes:</b> <code>/enable_like</code>\n"
                f"• {EMOJI['warning']} <b>Maintenance Mode:</b> <code>/maintenance</code>\n"
                f"• {EMOJI['success']} <b>End Maintenance:</b> <code>/end_maintenance</code>\n"
                f"• {EMOJI['deactivate']} <b>Leave Group:</b> <code>/leave [group_id]</code>\n"
                f"• {EMOJI['activate']} <b>Temporary Activate:</b> <code>/sid [group_id] [days]</code>\n"
                f"• {EMOJI['ban']} <b>Ban User:</b> <code>/ban_user [user_id] [reason]</code>\n"
                f"• {EMOJI['success']} <b>Unban User:</b> <code>/unban_user [user_id]</code>\n"
                f"• {EMOJI['photo']} <b>Set Video:</b> <code>/setvideo</code>\n\n"
            )
        
        caption += (
            f"╔═══════════════════════╗\n"
            f"║      📚 EXAMPLES      ║\n"
            f"╚═══════════════════════╝\n\n"
            
            f"<code>/2 1234567890</code>\n"
            f"<code>/3 1234567890</code>\n"
            f"<code>/4 1234567890</code>\n"
            f"<code>/5 1234567890</code>\n"
            f"<code>/6 1234567890</code>\n"
            f"<code>/info 2450675101</code>\n"
            f"<code>/like 2450675101</code>\n"
            f"<code>/friends 760840390</code>\n"
            f"<code>/spam_clan 3090773889</code>\n"
            f"<code>/visit 760840390</code>\n"
            f"<code>/baane 2450675101</code>\n"
            f"<code>/bio</code> (in private)\n"
            f"<code>/login 4388868414 mypassword123</code>\n"
            f"<code>/access ff90c07eb9815af30a43b4a9f6019516e0e4c703b44092516d0defa4cef51f2a</code>\n\n"
            
            f"╔═══════════════════════╗\n"
            f"║       ℹ️ ABOUT        ║\n"
            f"╚═══════════════════════╝\n\n"
            
            f"Developer: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
            f"Team: <b>D5M</b>\n"
            f"Version: <b>3.0 Premium</b>\n\n"
            
            f"🔥 <i>Free Fire Tools Bot</i> 🔥"
        )
    else:
        approved_groups = load_approved_groups()
        group_expiry = load_group_expiry()
        group_id_str = str(chat.id)
        is_active = group_id_str in approved_groups or (group_id_str in group_expiry and datetime.now(timezone.utc) < datetime.fromisoformat(group_expiry[group_id_str]))
        
        if is_active:
            caption = (
                f"╔═══════════════════════╗\n"
                f"║    🤖 BOT ACTIVATED   ║\n"
                f"╚═══════════════════════╝\n\n"
                f"• {EMOJI['invite']} <b>2 Player Squad:</b> <code>/2 ID</code>\n"
                f"• {EMOJI['invite']} <b>3 Player Squad:</b> <code>/3 ID</code>\n"
                f"• {EMOJI['invite']} <b>4 Player Squad:</b> <code>/4 ID</code>\n"
                f"• {EMOJI['invite']} <b>5 Player Squad:</b> <code>/5 ID</code>\n"
                f"• {EMOJI['invite']} <b>6 Player Squad:</b> <code>/6 ID</code>\n\n"
                f"• {EMOJI['player']} Get Info: <code>/info UID</code>\n"
                f"• {EMOJI['like']} Send Likes: <code>/like UID</code>\n"
                f"• {EMOJI['handshake']} Friend Spam: <code>/friends UID</code>\n"
                f"• {EMOJI['clan']} Clan Spam: <code>/spam_clan CLAN_ID</code>\n"
                f"• {EMOJI['visit']} Send Visits: <code>/visit UID</code>\n"
                f"• {EMOJI['deactivate']} Check Ban: <code>/baane UID</code>\n"
                f"• {EMOJI['edit']} Change Bio: <code>/bio</code> (in private)\n"
                f"• {EMOJI['login']} Convert Login: <code>/login ID PASSWORD</code>\n"
                f"• {EMOJI['key']} Convert Token: <code>/access ACCESS_TOKEN</code>\n\n"
                f"Dev: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"Team: D5M"
            )
        else:
            caption = (
                f"{EMOJI['warning']} <b>Bot is not activated in this group.</b>\n"
                f"Please contact <a href='https://t.me/AlliFF_BOT'>AlliFF</a> to activate the bot.\n\n"
                f"Developer: <a href='https://t.me/AlliFF_BOT'>AlliFF</a>\n"
                f"Team: <b>D5M</b>"
            )
    
    await update.message.reply_text(
        text=caption,
        parse_mode='HTML',
        disable_web_page_preview=True
    )


def main() -> None:
    print("🤖 Bot is running now...")
    
    application = Application.builder().token(TOKEN).connect_timeout(30).read_timeout(30).write_timeout(30).build()
    
    bio_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("bio", bio_command)],
        states={
            WAITING_FOR_METHOD: [
                CallbackQueryHandler(bio_method_callback)
            ],
            WAITING_FOR_ACCESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_access_token),
            ],
            WAITING_FOR_UID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_uid),
            ],
            WAITING_FOR_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password),
            ],
            WAITING_FOR_NEW_BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_bio),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_bio)],
    )
    
    video_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setvideo", set_video_command)],
        states={
            WAITING_FOR_VIDEO: [
                CallbackQueryHandler(video_callback, pattern="^(add_video|delete_video)$"),
                MessageHandler(filters.VIDEO, receive_video),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_video),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_video)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("like", like_command))
    application.add_handler(CommandHandler("friends", friends_command))
    application.add_handler(CommandHandler("spam_clan", spam_clan_command))
    application.add_handler(CommandHandler("visit", visit_command))
    application.add_handler(CommandHandler("baane", baane_command))
    application.add_handler(CommandHandler("getid", getid_command))
    application.add_handler(CommandHandler("activate", activate_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("login", login_command))
    application.add_handler(CommandHandler("access", access_command))
    application.add_handler(bio_conv_handler)
    application.add_handler(CommandHandler("disable_like", disable_like_command))
    application.add_handler(CommandHandler("enable_like", enable_like_command))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("end_maintenance", end_maintenance_command))
    application.add_handler(CommandHandler("leave", leave_group_command))
    application.add_handler(CommandHandler("sid", sid_command))
    application.add_handler(CommandHandler("ban_user", ban_user_command))
    application.add_handler(CommandHandler("unban_user", unban_user_command))
    application.add_handler(video_conv_handler)
    
    application.add_handler(CommandHandler("2", lambda u, c: invite_command_handler(u, c, "2")))
    application.add_handler(CommandHandler("3", lambda u, c: invite_command_handler(u, c, "3")))
    application.add_handler(CommandHandler("4", lambda u, c: invite_command_handler(u, c, "4")))
    application.add_handler(CommandHandler("5", lambda u, c: invite_command_handler(u, c, "5")))
    application.add_handler(CommandHandler("6", lambda u, c: invite_command_handler(u, c, "6")))
    
    application.add_handler(CallbackQueryHandler(copy_token_callback, pattern=r"^copy_token:"))
    application.add_handler(CallbackQueryHandler(close_message_callback, pattern=r"^close_msg"))

    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            poll_interval=0.5,
            timeout=30,
            drop_pending_updates=True
        )
    except Exception as e:
        print(f"Failed to run bot: {e}")
        time.sleep(10)
        main()


if __name__ == "__main__":
    main()