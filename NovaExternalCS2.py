version = "1.0"
title = f"[v{version}] Nova CS2"

import win32gui, time, json, os, threading, psutil, win32process, win32api, win32con, random, requests, win32console, ctypes
import dearpygui.dearpygui as dpg
import pyMeow as pm
import math
import platform
from pypresence import Presence
import serial
import serial.tools.list_ports

user32 = ctypes.WinDLL("user32")
gdi32 = ctypes.WinDLL("gdi32")
kernel32 = ctypes.WinDLL("kernel32")

# SendInput structures
PUL = ctypes.POINTER(ctypes.c_ulong)
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("mi", MOUSEINPUT)
    ]
    INPUT_MOUSE = 0

# SendInput constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

def send_mouse_move(dx, dy, use_arduino=False, serial_port=None):
    """Send mouse movement either via SendInput or Arduino."""
    if use_arduino and serial_port:
        try:
            command = f"MOVE {int(dx)} {int(dy)}\n"
            serial_port.write(command.encode())
            serial_port.flush()
            print(f"Arduino MOVE command sent: {command.strip()}")
        except Exception as e:
            print(f"Arduino MOVE error: {e}")
            pass
    else:
        input_struct = INPUT()
        input_struct.type = INPUT.INPUT_MOUSE
        input_struct.mi.dx = int(dx)
        input_struct.mi.dy = int(dy)
        input_struct.mi.dwFlags = MOUSEEVENTF_MOVE
        user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))

def send_mouse_click(down, use_arduino=False, serial_port=None):
    """Send left mouse click (down or up) using either SendInput or Arduino."""
    if use_arduino and serial_port:
        try:
            command = f"CLICK {'DOWN' if down else 'UP'}\n"
            serial_port.write(command.encode())
            serial_port.flush()
            print(f"Arduino CLICK command sent: {command.strip()}")
        except Exception as e:
            print(f"Arduino CLICK error: {e}")
            pass
    else:
        input_struct = INPUT()
        input_struct.type = INPUT.INPUT_MOUSE
        input_struct.mi.dwFlags = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
        user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))

configFilePath = os.path.join(os.path.dirname(__file__), "NovaCS2.json")

class configListener(dict):
    def __init__(self, initialDict):
        for k, v in initialDict.items():
            if isinstance(v, dict):
                initialDict[k] = configListener(v)
        super().__init__(initialDict)

    def __setitem__(self, item, value):
        if isinstance(value, dict):
            value = configListener(value)
        super().__setitem__(item, value)
        try:
            if os.path.isdir(os.path.dirname(configFilePath)):
                json.dump(self, open(configFilePath, "w", encoding="utf-8"), indent=4)
        except:
            pass

class Colors:
    white = pm.get_color("white")
    whiteWatermark = pm.get_color("#f5f5ff")
    black = pm.get_color("black")
    blackFade = pm.fade_color(black, 0.6)
    red = pm.get_color("#e03636")
    green = pm.get_color("#43e06d")
    purple = pm.get_color("#ff00ff")
    dark_purple = pm.get_color("#4b0082")
    ui_background = pm.get_color("#1A4A8A")

class Offsets:
    m_pBoneArray = 496
    m_aimPunchAngle = 0x14C8
    m_iszPlayerName = 0x638
    m_iHealth = 0x32C
    m_iTeamNum = 0x3C4
    m_vOldOrigin = 0x124
    m_pGameSceneNode = 0x310
    m_bDormant = 0xE9
    m_hPlayerPawn = 0x7E4
    m_flFOV = 0x1694
    m_pWeaponServices = 0x1128
    m_pWeapon = 0x1A8
    m_iItemDefinitionIndex = 0x1A6
    m_bIsBot = 0x7E8
    m_fFlags = 0x104
    dwViewMatrix = 0x192D1A0
    dwEntityList = 0x18C7D68
    dwLocalPlayerController = 0x191C618
    dwLocalPlayerPawn = 0x173B848

class Entity:
    def __init__(self, ptr, pawnPtr, proc):
        self.ptr = ptr
        self.pawnPtr = pawnPtr
        self.proc = proc
        self.pos2d = None
        self.headPos2d = None

    @property
    def name(self):
        try:
            return pm.r_string(self.proc, self.ptr + Offsets.m_iszPlayerName)
        except:
            return "Unknown"

    @property
    def health(self):
        try:
            return pm.r_int(self.proc, self.pawnPtr + Offsets.m_iHealth)
        except:
            return 0

    @property
    def team(self):
        try:
            return pm.r_int(self.proc, self.pawnPtr + Offsets.m_iTeamNum)
        except:
            return 0

    @property
    def pos(self):
        try:
            return pm.r_vec3(self.proc, self.pawnPtr + Offsets.m_vOldOrigin)
        except:
            return {"x": 0, "y": 0, "z": 0}

    @property
    def isDormant(self):
        try:
            return pm.r_bool(self.proc, self.pawnPtr + Offsets.m_bDormant)
        except:
            return True

    @property
    def isBot(self):
        try:
            return pm.r_bool(self.proc, self.ptr + Offsets.m_bIsBot)
        except:
            return False

    @property
    def flags(self):
        try:
            return pm.r_int(self.proc, self.pawnPtr + Offsets.m_fFlags)
        except:
            return 0

    @property
    def weapon(self):
        try:
            weapon_services = pm.r_int64(self.proc, self.pawnPtr + Offsets.m_pWeaponServices)
            weapon_ptr = pm.r_int64(self.proc, weapon_services + Offsets.m_pWeapon)
            if not weapon_ptr:
                return "None"
            item_index = pm.r_int(self.proc, weapon_ptr + Offsets.m_iItemDefinitionIndex)
            weapon_map = {
                1: "Desert Eagle", 2: "Dual Berettas", 3: "Five-SeveN", 4: "Glock-18",
                7: "AK-47", 8: "AUG", 9: "AWP", 10: "FAMAS", 11: "G3SG1",
                13: "Galil AR", 14: "M249", 16: "M4A4", 17: "MAC-10", 19: "P90",
                23: "MP5-SD", 24: "UMP-45", 25: "XM1014", 26: "PP-Bizon", 27: "MAG-7",
                28: "Negev", 29: "Sawed-Off", 30: "Tec-9", 31: "Taser", 32: "P2000",
                33: "MP7", 34: "MP9", 35: "Nova", 36: "P250", 38: "SCAR-20",
                39: "SG 553", 40: "SSG 08", 61: "USP-S", 63: "CZ75-Auto", 64: "R8 Revolver",
                42: "Knife", 43: "Flashbang", 44: "HE Grenade", 45: "Smoke Grenade",
                46: "Molotov", 47: "Decoy Grenade", 48: "Incendiary Grenade"
            }
            return weapon_map.get(item_index, "None")
        except:
            return "None"

    def bonePos(self, bone):
        try:
            gameScene = pm.r_int64(self.proc, self.pawnPtr + Offsets.m_pGameSceneNode)
            boneArrayPtr = pm.r_int64(self.proc, gameScene + Offsets.m_pBoneArray)
            return pm.r_vec3(self.proc, boneArrayPtr + bone * 32)
        except:
            return {"x": 0, "y": 0, "z": 0}

    def wts(self, viewMatrix):
        try:
            success, self.pos2d = pm.world_to_screen_noexc(viewMatrix, self.pos, 1)
            success_head, self.headPos2d = pm.world_to_screen_noexc(viewMatrix, self.bonePos(6), 1)
            return success and success_head and self.pos2d["x"] > 0 and self.pos2d["y"] > 0 and self.headPos2d["x"] > 0 and self.headPos2d["y"] > 0
        except:
            return False

class NovaCS2:
    def __init__(self):
        self.config = {
            "version": version,
            "esp": {
                "enabled": False,
                "bind": 0,
                "box": True,
                "boxBackground": True,
                "boxRounding": 0.2,
                "skeleton": True,
                "redHead": True,
                "snapline": True,
                "name": True,
                "health": True,
                "distance": True
            },
            "triggerBot": {
                "enabled": False,
                "bind": 0,
                "onlyEnemies": True,
                "delay": 0,
            },
            "aimbot": {
                "enabled": False,
                "fov": 60.0,
                "smooth": 1.0,
                "sensitivity": 1.0,
                "onlyEnemies": True,
                "bone": 6,
                "bone_selection": "Head",
                "show_fov": False,
                "wall_check": True,
                "anti_recoil": False
            },
            "misc": {
                "noFlash": False,
                "radar": True,
                "fov_changer": {
                    "enabled": False,
                    "value": 90
                },
                "weapon_esp": False,
                "bot_indicator": False,
                "bunny_hop": {
                    "enabled": False,
                    "bind": 0
                },
                "discord_rpc": {
                    "enabled": False
                },
                "fps_overlay": {
                    "enabled": False
                }
            },
            "settings": {
                "saveSettings": True,
                "streamProof": False
            },
            "arduino": {
                "enabled": False,
                "port": "",
                "input_method": "Windows"
            }
        }

        self.anti_recoil_available = True
        self.fov_changer_available = True
        self.weapon_esp_available = True
        self.bunny_hop_available = True
        self.discord_rpc_available = True
        self.arduino_serial = None
        if os.path.isfile(configFilePath):
            try:
                config = json.loads(open(configFilePath, encoding="utf-8").read())
                isConfigOk = True
                for key in self.config:
                    if not key in config or len(self.config[key]) != len(config[key]):
                        isConfigOk = False
                        break
                if isConfigOk and config["version"] == version:
                    self.config = config
            except:
                pass

        self.config = configListener(self.config)
        self.guiWindowHandle = None
        self.overlayWindowHandle = None
        self.overlayThreadExists = False
        self.localTeam = None
        self.espColor = pm.new_color_float(0.0, 0.749, 1.0, 0.8)
        self.espBackGroundColor = pm.fade_color(self.espColor, 0.3)
        self.discord_rpc = None
        self.last_frame_time = time.time()
        self.frame_count = 0
        self.fps = 0
        self.run()

    def isCsOpened(self):
        while True:
            if not pm.process_running(self.proc):
                if self.discord_rpc:
                    self.discord_rpc.close()
                if self.arduino_serial:
                    self.arduino_serial.close()
                os._exit(0)
            time.sleep(3)

    def windowListener(self):
        while True:
            try:
                self.focusedProcess = psutil.Process(win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[-1]).name()
            except:
                self.focusedProcess = ""
            time.sleep(0.5)

    def set_fov(self):
        while True:
            if not self.config["misc"]["fov_changer"]["enabled"] or not self.fov_changer_available:
                break
            if self.focusedProcess != "cs2.exe":
                time.sleep(1)
                continue
            try:
                player = pm.r_int64(self.proc, self.mod + Offsets.dwLocalPlayerPawn)
                pm.w_float(self.proc, player + Offsets.m_flFOV, self.config["misc"]["fov_changer"]["value"])
            except:
                pass
            time.sleep(0.1)

    def bunny_hop(self):
        while True:
            if not self.config["misc"]["bunny_hop"]["enabled"] or not self.bunny_hop_available:
                break
            if self.focusedProcess != "cs2.exe":
                time.sleep(1)
                continue
            if win32api.GetAsyncKeyState(self.config["misc"]["bunny_hop"]["bind"]) & 0x8000 == 0:
                time.sleep(0.001)
                continue
            print(f"BunnyHop triggered with bind: {chr(self.config['misc']['bunny_hop']['bind'])}")
            try:
                player = pm.r_int64(self.proc, self.mod + Offsets.dwLocalPlayerPawn)
                flags = pm.r_int(self.proc, player + Offsets.m_fFlags)
                if flags & 1:
                    win32api.keybd_event(win32con.VK_SPACE, 0, 0, 0)
                    time.sleep(0.01)
                    win32api.keybd_event(win32con.VK_SPACE, 0, win32con.KEYEVENTF_KEYUP, 0)
            except:
                pass
            time.sleep(0.01)

    def discord_rpc_update(self):
        while True:
            if not self.config["misc"]["discord_rpc"]["enabled"] or not self.discord_rpc_available:
                if self.discord_rpc:
                    self.discord_rpc.close()
                    self.discord_rpc = None
                break
            if not self.discord_rpc:
                try:
                    self.discord_rpc = Presence("000000000000000000")
                    self.discord_rpc.connect()
                except:
                    self.discord_rpc_available = False
                    self.config["misc"]["discord_rpc"]["enabled"] = False
                    break
            try:
                self.discord_rpc.update(
                    state="Using Nova CS2",
                    details="Playing Counter-Strike 2",
                    start=int(time.time())
                )
            except:
                self.discord_rpc_available = False
                self.config["misc"]["discord_rpc"]["enabled"] = False
                if self.discord_rpc:
                    self.discord_rpc.close()
                    self.discord_rpc = None
                break
            time.sleep(15)

    def run(self):
        print("Waiting for CS2...")
        while True:
            time.sleep(1)
            try:
                self.proc = pm.open_process("cs2.exe")
                self.mod = pm.get_module(self.proc, "client.dll")["base"]
                break
            except:
                pass

        print("Starting Nova CS2!")
        os.system("cls")

        try:
            offsetsName = ["dwViewMatrix", "dwEntityList", "dwLocalPlayerController", "dwLocalPlayerPawn"]
            offsets = requests.get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json").json()
            [setattr(Offsets, k, offsets["client.dll"][k]) for k in offsetsName]
            clientDllName = {
                "m_iIDEntIndex": "C_CSPlayerPawnBase",
                "m_hPlayerPawn": "CCSPlayerController",
                "m_fFlags": "C_BaseEntity",
                "m_iszPlayerName": "CBasePlayerController",
                "m_iHealth": "C_BaseEntity",
                "m_iTeamNum": "C_BaseEntity",
                "m_vOldOrigin": "C_BasePlayerPawn",
                "m_pGameSceneNode": "C_BaseEntity",
                "m_bDormant": "CGameSceneNode",
                "m_aimPunchAngle": "C_CSPlayerPawnBase",
                "m_flFOV": "C_CSPlayerPawnBase",
                "m_pWeaponServices": "C_CSPlayerPawnBase",
                "m_pWeapon": "C_CSWeaponBase",
                "m_iItemDefinitionIndex": "C_EconEntity",
                "m_bIsBot": "CCSPlayerController"
            }
            clientDll = requests.get("https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json").json()
            try:
                for k in clientDllName:
                    setattr(Offsets, k, clientDll["client.dll"]["classes"][clientDllName[k]]["fields"][k])
            except KeyError as e:
                print(f"Warning: Failed to retrieve offset {e}. Using fallback values.")
                if str(e) == "'m_aimPunchAngle'":
                    self.anti_recoil_available = False
                    self.config["aimbot"]["anti_recoil"] = False
                if str(e) == "'m_flFOV'":
                    self.fov_changer_available = False
                    self.config["misc"]["fov_changer"]["enabled"] = False
                if str(e) in ["'m_pWeaponServices'", "'m_pWeapon'", "'m_iItemDefinitionIndex'"]:
                    self.weapon_esp_available = False
                    self.config["misc"]["weapon_esp"] = False
                if str(e) == "'m_bIsBot'":
                    self.config["misc"]["bot_indicator"] = False
                if str(e) == "'m_fFlags'":
                    self.bunny_hop_available = False
                    self.config["misc"]["bunny_hop"]["enabled"] = False
        except Exception as e:
            print(f"Error retrieving offsets: {e}. Using fallback values for m_aimPunchAngle, m_flFOV, weapon, bot, and flags offsets.")
            self.anti_recoil_available = False
            self.fov_changer_available = False
            self.weapon_esp_available = False
            self.bunny_hop_available = False
            self.config["aimbot"]["anti_recoil"] = False
            self.config["misc"]["fov_changer"]["enabled"] = False
            self.config["misc"]["weapon_esp"] = False
            self.config["misc"]["bot_indicator"] = False
            self.config["misc"]["bunny_hop"]["enabled"] = False

        threading.Thread(target=self.isCsOpened, daemon=True).start()
        threading.Thread(target=self.windowListener, daemon=True).start()
        threading.Thread(target=self.espBindListener, daemon=True).start()
        if self.config["esp"]["enabled"] or self.config["misc"]["radar"] or self.config["misc"]["fps_overlay"]["enabled"]:
            threading.Thread(target=self.overlay, daemon=True).start()
        if self.config["triggerBot"]["enabled"]:
            threading.Thread(target=self.triggerBot, daemon=True).start()
        if self.config["aimbot"]["enabled"]:
            threading.Thread(target=self.aimbot, daemon=True).start()
        if self.config["misc"]["noFlash"]:
            self.noFlash()
        if self.config["misc"]["fov_changer"]["enabled"] and self.fov_changer_available:
            threading.Thread(target=self.set_fov, daemon=True).start()
        if self.config["misc"]["bunny_hop"]["enabled"] and self.bunny_hop_available:
            threading.Thread(target=self.bunny_hop, daemon=True).start()
        if self.config["misc"]["discord_rpc"]["enabled"] and self.discord_rpc_available:
            threading.Thread(target=self.discord_rpc_update, daemon=True).start()

    def espBindListener(self):
        while not hasattr(self, "focusedProcess"):
            time.sleep(0.1)
        last_state = 0
        while True:
            if self.focusedProcess != "cs2.exe":
                time.sleep(1)
                continue
            time.sleep(0.001)
            bind = self.config["esp"]["bind"]
            if bind == 0:
                continue
            current_state = win32api.GetAsyncKeyState(bind)
            if current_state & 0x8000 and not last_state & 0x8000:
                print(f"ESP toggled with bind: {chr(bind)}")
                self.config["esp"]["enabled"] = not self.config["esp"]["enabled"]
                if (self.config["esp"]["enabled"] or self.config["misc"]["radar"] or self.config["misc"]["fps_overlay"]["enabled"]) and not self.overlayThreadExists:
                    threading.Thread(target=self.overlay, daemon=True).start()
                try:
                    dpg.set_value(checkboxToggleEsp, self.config["esp"]["enabled"])
                except:
                    pass
                while win32api.GetAsyncKeyState(bind) & 0x8000:
                    time.sleep(0.001)
            last_state = current_state

    def getEntities(self):
        entList = pm.r_int64(self.proc, self.mod + Offsets.dwEntityList)
        local = pm.r_int64(self.proc, self.mod + Offsets.dwLocalPlayerController)
        try:
            self.localTeam = pm.r_int(self.proc, local + Offsets.m_iTeamNum)
        except:
            self.localTeam = 0
        for i in range(1, 65):
            try:
                entryPtr = pm.r_int64(self.proc, entList + (8 * (i & 0x7FFF) >> 9) + 16)
                controllerPtr = pm.r_int64(self.proc, entryPtr + 120 * (i & 0x1FF))
                if controllerPtr == local:
                    continue
                controllerPawnPtr = pm.r_int64(self.proc, controllerPtr + Offsets.m_hPlayerPawn)
                listEntryPtr = pm.r_int64(self.proc, entList + 0x8 * ((controllerPawnPtr & 0x7FFF) >> 9) + 16)
                pawnPtr = pm.r_int64(self.proc, listEntryPtr + 120 * (controllerPawnPtr & 0x1FF))
                yield Entity(controllerPtr, pawnPtr, self.proc)
            except:
                continue

    def is_visible(self, local_pos, target_pos):
        try:
            distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(local_pos.values(), target_pos.values())))
            if distance > 3000:
                return False
            height_diff = abs(local_pos["z"] - target_pos["z"])
            if height_diff > 200:
                return False
            return True
        except:
            return False

    def calculate_distance(self, local_pos, target_pos):
        try:
            distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(local_pos.values(), target_pos.values())))
            return round(distance / 39.37, 1)
        except:
            return 0.0

    def overlay(self):
        self.overlayThreadExists = True
        while not hasattr(self, "focusedProcess"):
            time.sleep(0.1)
        pm.overlay_init("Counter-Strike 2", fps=144, title="".join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(8)), trackTarget=True)
        self.overlayWindowHandle = pm.get_window_handle()
        if self.config["settings"]["streamProof"]:
            user32.SetWindowDisplayAffinity(self.overlayWindowHandle, 0x00000011)
        else:
            user32.SetWindowDisplayAffinity(self.overlayWindowHandle, 0x00000000)
        while pm.overlay_loop():
            if self.focusedProcess != "cs2.exe":
                time.sleep(1)
                pm.begin_drawing()
                pm.end_drawing()
                continue
            pm.begin_drawing()
            try:
                viewMatrix = pm.r_floats(self.proc, self.mod + Offsets.dwViewMatrix, 16)
                screen_width = pm.get_screen_width()
                screen_height = pm.get_screen_height()
                local_player = pm.r_int64(self.proc, self.mod + Offsets.dwLocalPlayerPawn)
                local_pos = pm.r_vec3(self.proc, local_player + Offsets.m_vOldOrigin)

                # Calculate FPS
                if self.config["misc"]["fps_overlay"]["enabled"]:
                    current_time = time.time()
                    self.frame_count += 1
                    if current_time - self.last_frame_time >= 1.0:
                        self.fps = self.frame_count / (current_time - self.last_frame_time)
                        self.frame_count = 0
                        self.last_frame_time = current_time
                    pm.draw_text(
                        f"FPS: {int(self.fps)}",
                        10, 10, 15, Colors.white
                    )

                if self.config["esp"]["enabled"]:
                    for ent in self.getEntities():
                        if ent.isDormant or ent.health <= 0:
                            continue
                        if not ent.wts(viewMatrix):
                            continue
                        head = ent.pos2d["y"] - ent.headPos2d["y"]
                        width = head / 2
                        center = width / 2
                        xStart = ent.headPos2d["x"] - center
                        yStart = ent.headPos2d["y"] - center / 2

                        if self.config["esp"]["box"]:
                            pm.draw_rectangle_rounded_lines(
                                xStart, yStart, width, head + center / 2,
                                self.config["esp"]["boxRounding"], 1, self.espColor, 1.2
                            )
                        if self.config["esp"]["boxBackground"]:
                            pm.draw_rectangle_rounded(
                                xStart, yStart, width, head + center / 2,
                                self.config["esp"]["boxRounding"], 1, self.espBackGroundColor
                            )

                        if self.config["esp"]["redHead"]:
                            pm.draw_circle_sector(
                                ent.headPos2d["x"], ent.headPos2d["y"], center / 3,
                                0, 360, 0, Colors.red
                            )

                        if self.config["esp"]["skeleton"]:
                            try:
                                bones = {
                                    "neck": pm.world_to_screen(viewMatrix, ent.bonePos(5), 1),
                                    "shoulderR": pm.world_to_screen(viewMatrix, ent.bonePos(8), 1),
                                    "shoulderL": pm.world_to_screen(viewMatrix, ent.bonePos(13), 1),
                                    "elbowR": pm.world_to_screen(viewMatrix, ent.bonePos(9), 1),
                                    "elbowL": pm.world_to_screen(viewMatrix, ent.bonePos(14), 1),
                                    "handR": pm.world_to_screen(viewMatrix, ent.bonePos(11), 1),
                                    "handL": pm.world_to_screen(viewMatrix, ent.bonePos(16), 1),
                                    "waist": pm.world_to_screen(viewMatrix, ent.bonePos(0), 1),
                                    "kneeR": pm.world_to_screen(viewMatrix, ent.bonePos(23), 1),
                                    "kneeL": pm.world_to_screen(viewMatrix, ent.bonePos(26), 1),
                                    "footR": pm.world_to_screen(viewMatrix, ent.bonePos(24), 1),
                                    "footL": pm.world_to_screen(viewMatrix, ent.bonePos(27), 1)
                                }
                                for start, end in [
                                    ("neck", "shoulderR"), ("neck", "shoulderL"),
                                    ("shoulderL", "elbowL"), ("shoulderR", "elbowR"),
                                    ("elbowR", "handR"), ("elbowL", "handL"),
                                    ("neck", "waist"), ("waist", "kneeR"),
                                    ("waist", "kneeL"), ("kneeL", "footL"),
                                    ("kneeR", "footR")
                                ]:
                                    if bones[start][0] and bones[end][0]:
                                        pm.draw_line(
                                            bones[start][1]["x"], bones[start][1]["y"],
                                            bones[end][1]["x"], bones[end][1]["y"],
                                            self.espColor, 1
                                        )
                            except:
                                pass

                        if self.config["esp"]["name"]:
                            y_offset = -15
                            pm.draw_text(
                                ent.name,
                                xStart + center - pm.measure_text(ent.name, 15) / 2,
                                yStart + y_offset,
                                15, Colors.white
                            )
                            y_offset -= 15
                            if self.config["esp"]["distance"]:
                                distance = self.calculate_distance(local_pos, ent.pos)
                                distance_text = f"{distance}m"
                                pm.draw_text(
                                    distance_text,
                                    xStart + center - pm.measure_text(distance_text, 12) / 2,
                                    yStart + y_offset,
                                    12, Colors.white
                                )
                                y_offset -= 15
                            if self.config["misc"]["weapon_esp"] and self.weapon_esp_available:
                                pm.draw_text(
                                    ent.weapon,
                                    xStart + center - pm.measure_text(ent.weapon, 12) / 2,
                                    yStart + y_offset,
                                    12, self.espColor
                                )
                                y_offset -= 15
                            if self.config["misc"]["bot_indicator"]:
                                text = "Bot" if ent.isBot else "Player"
                                pm.draw_text(
                                    text,
                                    xStart + center - pm.measure_text(text, 12) / 2,
                                    yStart + y_offset,
                                    12, self.espColor
                                )

                        if self.config["esp"]["snapline"]:
                            try:
                                _, head_pos = pm.world_to_screen_noexc(viewMatrix, ent.bonePos(6), 1)
                                pm.draw_line(
                                    screen_width / 2, screen_height - 50,
                                    head_pos["x"], head_pos["y"],
                                    self.espColor, 1
                                )
                            except:
                                pass

                if self.config["misc"]["radar"]:
                    radar_size = 150
                    radar_x = screen_width - radar_size - 10
                    radar_y = 10
                    pm.draw_rectangle_rounded(radar_size, radar_y, radar_size, radar_size, 0.2, 4, Colors.blackFade)
                    pm.draw_rectangle_rounded_lines(radar_x, radar_y, radar_size, radar_size, 0.2, 4, Colors.dark_purple, 2)
                    pm.draw_circle(radar_x + radar_size / 2, radar_y + radar_size / 2, 3, Colors.green, 1.0)
                    try:
                        for ent in self.getEntities():
                            if ent.isDormant or ent.health <= 0 or self.localTeam == ent.team:
                                continue
                            rel_pos = {
                                "x": ent.pos["x"] - local_pos["x"],
                                "y": ent.pos["y"] - local_pos["y"],
                                "z": ent.pos["z"] - local_pos["z"]
                            }
                            scale = radar_size / 1000
                            radar_pos_x = radar_x + radar_size / 2 + rel_pos["x"] * scale
                            radar_pos_y = radar_y + radar_size / 2 - rel_pos["y"] * scale
                            radar_pos_x = max(radar_x + 5, min(radar_x + radar_size - 5, radar_pos_x))
                            radar_pos_y = max(radar_y + 5, min(radar_y + radar_size - 5, radar_pos_y))
                            pm.draw_circle(radar_pos_x, radar_pos_y, 3, Colors.red, 1.0)
                    except:
                        pass

            except:
                pass
            pm.end_drawing()
            if not (self.config["esp"]["enabled"] or self.config["misc"]["radar"] or self.config["misc"]["fps_overlay"]["enabled"]):
                pm.overlay_close()
                break
        self.overlayThreadExists = False

    def aimbot(self):
        bone_map = {
            "Head": 6,
            "Neck": 5,
            "Chest": 2,
            "Pelvis": 0
        }
        last_punch = {"x": 0, "y": 0}
        while not hasattr(self, "focusedProcess"):
            time.sleep(0.1)
        last_state = 0
        while True:
            time.sleep(0.001)
            if not self.config["aimbot"]["enabled"]:
                break
            if self.focusedProcess != "cs2.exe":
                time.sleep(1)
                continue
            current_state = win32api.GetAsyncKeyState(win32con.VK_RBUTTON)
            if not (current_state & 0x8000):
                last_state = current_state
                continue
            if current_state & 0x8000 and not last_state & 0x8000:
                print("DEBUG: Aimbot activated with right mouse button")
            try:
                viewMatrix = pm.r_floats(self.proc, self.mod + Offsets.dwViewMatrix, 16)
                player = pm.r_int64(self.proc, self.mod + Offsets.dwLocalPlayerPawn)
                local_pos = pm.r_vec3(self.proc, player + Offsets.m_vOldOrigin)
                screen_center_x = pm.get_screen_width() / 2
                screen_center_y = pm.get_screen_height() / 2
                closest_dist = float('inf')
                target_x, target_y = 0, 0
                for ent in self.getEntities():
                    if ent.isDormant or ent.health <= 0 or (self.config["aimbot"]["onlyEnemies"] and self.localTeam == ent.team):
                        continue
                    if ent.wts(viewMatrix):
                        if self.config["aimbot"]["wall_check"]:
                            if not self.is_visible(local_pos, ent.bonePos(bone_map[self.config["aimbot"]["bone_selection"]])):
                                continue
                        bone_id = bone_map[self.config["aimbot"]["bone_selection"]]
                        bone_pos = pm.world_to_screen_noexc(viewMatrix, ent.bonePos(bone_id), 1)[1]
                        dist = math.sqrt((bone_pos["x"] - screen_center_x) ** 2 + (bone_pos["y"] - screen_center_y) ** 2)
                        if dist < closest_dist and dist < self.config["aimbot"]["fov"] * pm.get_screen_width() / 90:
                            closest_dist = dist
                            target_x, target_y = bone_pos["x"], bone_pos["y"]
                if closest_dist != float('inf'):
                    dx = (target_x - screen_center_x) / (self.config["aimbot"]["smooth"] / self.config["aimbot"]["sensitivity"])
                    dy = (target_y - screen_center_y) / (self.config["aimbot"]["smooth"] / self.config["aimbot"]["sensitivity"])
                    if self.config["aimbot"]["anti_recoil"] and self.anti_recoil_available and win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
                        try:
                            aim_punch = pm.r_vec2(self.proc, player + Offsets.m_aimPunchAngle)
                            dx += (aim_punch["x"] - last_punch["x"]) * -2
                            dy += (aim_punch["y"] - last_punch["y"]) * -2
                            last_punch = aim_punch
                        except:
                            pass
                    send_mouse_move(dx, dy, self.config["arduino"]["enabled"], self.arduino_serial)
                elif self.config["aimbot"]["anti_recoil"] and self.anti_recoil_available and win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
                    try:
                        aim_punch = pm.r_vec2(self.proc, player + Offsets.m_aimPunchAngle)
                        dx = (aim_punch["x"] - last_punch["x"]) * -2
                        dy = (aim_punch["y"] - last_punch["y"]) * -2
                        last_punch = aim_punch
                        send_mouse_move(dy * 2, dx * 2, self.config["arduino"]["enabled"], self.arduino_serial)
                    except:
                        pass
            except:
                pass
            last_state = current_state

    def triggerBot(self):
        while not hasattr(self, "focusedProcess"):
            time.sleep(0.1)
        last_state = 0
        while True:
            time.sleep(0.001)
            if not self.config["triggerBot"]["enabled"]:
                break
            if self.focusedProcess != "cs2.exe":
                time.sleep(1)
                continue
            current_state = win32api.GetAsyncKeyState(self.config["triggerBot"]["bind"])
            if current_state & 0x8000 and not last_state & 0x8000:
                print(f"TriggerBot activated with bind: {chr(self.config['triggerBot']['bind'])}")
            if current_state & 0x8000 == 0:
                last_state = current_state
                continue
            try:
                player = pm.r_int64(self.proc, self.mod + Offsets.dwLocalPlayerPawn)
                entityId = pm.r_int(self.proc, player + Offsets.m_iIDEntIndex)
                if entityId > 0:
                    entList = pm.r_int64(self.proc, self.mod + Offsets.dwEntityList)
                    entEntry = pm.r_int64(self.proc, entList + 0x8 * (entityId >> 9) + 0x10)
                    entity = pm.r_int64(self.proc, entEntry + 120 * (entityId & 0x1FF))
                    entityTeam = pm.r_int(self.proc, entity + Offsets.m_iTeamNum)
                    playerTeam = pm.r_int(self.proc, player + Offsets.m_iTeamNum)
                    if self.config["triggerBot"]["onlyEnemies"] and playerTeam == entityTeam:
                        continue
                    entityHp = pm.r_int(self.proc, entity + Offsets.m_iHealth)
                    if entityHp > 0:
                        time.sleep(self.config["triggerBot"]["delay"])
                        send_mouse_click(True, self.config["arduino"]["enabled"], self.arduino_serial)
                        time.sleep(0.01)
                        send_mouse_click(False, self.config["arduino"]["enabled"], self.arduino_serial)
            except:
                pass
            last_state = current_state

    def noFlash(self):
        return

if __name__ == "__main__":
    import asyncio
    async def main():
        if os.name != "nt":
            print("Nova CS2 is only working on Windows.")
            os._exit(0)
        novaCS2Class = NovaCS2()
        win32gui.ShowWindow(win32console.GetConsoleWindow(), win32con.SW_HIDE)
        uiWidth = 900
        uiHeight = 600
        dpg.create_context()

        def toggleEsp(id, value):
            novaCS2Class.config["esp"]["enabled"] = value
            if value and not novaCS2Class.overlayThreadExists:
                threading.Thread(target=novaCS2Class.overlay, daemon=True).start()

        waitingForKeyEsp = False
        def statusBindEsp(id):
            global waitingForKeyEsp
            if not waitingForKeyEsp:
                with dpg.handler_registry(tag="Esp Bind Handler"):
                    dpg.add_key_press_handler(callback=setBindEsp)
                dpg.set_item_label(buttonBindEsp, "...")
                waitingForKeyEsp = True

        def setBindEsp(id, value):
            global waitingForKeyEsp
            if waitingForKeyEsp and value != 0:
                novaCS2Class.config["esp"]["bind"] = value
                dpg.set_item_label(buttonBindEsp, f"Bind: {chr(value)}")
                dpg.delete_item("Esp Bind Handler")
                waitingForKeyEsp = False
                print(f"ESP bind set to: {chr(value)}")

        def toggleEspBox(id, value):
            novaCS2Class.config["esp"]["box"] = value

        def toggleEspBoxBackground(id, value):
            novaCS2Class.config["esp"]["boxBackground"] = value

        def toggleEspSkeleton(id, value):
            novaCS2Class.config["esp"]["skeleton"] = value

        def toggleEspRedHead(id, value):
            novaCS2Class.config["esp"]["redHead"] = value

        def toggleEspSnapline(id, value):
            novaCS2Class.config["esp"]["snapline"] = value

        def toggleEspName(id, value):
            novaCS2Class.config["esp"]["name"] = value

        def toggleEspHealth(id, value):
            novaCS2Class.config["esp"]["health"] = value

        def toggleEspDistance(id, value):
            novaCS2Class.config["esp"]["distance"] = value

        def setEspBoxRounding(id, value):
            novaCS2Class.config["esp"]["boxRounding"] = value

        def toggleTriggerBot(id, value):
            novaCS2Class.config["triggerBot"]["enabled"] = value
            if value:
                threading.Thread(target=novaCS2Class.triggerBot, daemon=True).start()

        waitingForKeyTriggerBot = False
        def statusBindTriggerBot(id):
            global waitingForKeyTriggerBot
            if not waitingForKeyTriggerBot:
                with dpg.handler_registry(tag="TriggerBot Bind Handler"):
                    dpg.add_key_press_handler(callback=setBindTriggerBot)
                dpg.set_item_label(buttonBindTriggerBot, "...")
                waitingForKeyTriggerBot = True

        def setBindTriggerBot(id, value):
            global waitingForKeyTriggerBot
            if waitingForKeyTriggerBot and value != 0:
                novaCS2Class.config["triggerBot"]["bind"] = value
                dpg.set_item_label(buttonBindTriggerBot, f"Bind: {chr(value)}")
                dpg.delete_item("TriggerBot Bind Handler")
                waitingForKeyTriggerBot = False
                print(f"TriggerBot bind set to: {chr(value)}")

        def toggleTriggerBotOnlyEnemies(id, value):
            novaCS2Class.config["triggerBot"]["onlyEnemies"] = value

        def sliderTriggerBotDelay(id, value):
            novaCS2Class.config["triggerBot"]["delay"] = value

        def toggleAimbot(id, value):
            novaCS2Class.config["aimbot"]["enabled"] = value
            if value:
                threading.Thread(target=novaCS2Class.aimbot, daemon=True).start()

        def setAimbotFov(id, value):
            novaCS2Class.config["aimbot"]["fov"] = value

        def setAimbotSmooth(id, value):
            novaCS2Class.config["aimbot"]["smooth"] = value

        def setAimbotSensitivity(id, value):
            novaCS2Class.config["aimbot"]["sensitivity"] = value

        def toggleAimbotOnlyEnemies(id, value):
            novaCS2Class.config["aimbot"]["onlyEnemies"] = value

        def setAimbotBone(id, value):
            novaCS2Class.config["aimbot"]["bone_selection"] = value

        def toggleAimbotShowFov(id, value):
            novaCS2Class.config["aimbot"]["show_fov"] = value
            if value and not novaCS2Class.overlayThreadExists:
                threading.Thread(target=novaCS2Class.overlay, daemon=True).start()

        def toggleAimbotWallCheck(id, value):
            novaCS2Class.config["aimbot"]["wall_check"] = value

        def toggleAimbotAntiRecoil(id, value):
            novaCS2Class.config["aimbot"]["anti_recoil"] = value

        def toggleNoFlash(id, value):
            novaCS2Class.config["misc"]["noFlash"] = value
            novaCS2Class.noFlash()

        def toggleRadar(id, value):
            novaCS2Class.config["misc"]["radar"] = value
            if value and not novaCS2Class.overlayThreadExists:
                threading.Thread(target=novaCS2Class.overlay, daemon=True).start()

        def toggleFovChanger(id, value):
            novaCS2Class.config["misc"]["fov_changer"]["enabled"] = value
            if value and novaCS2Class.fov_changer_available:
                threading.Thread(target=novaCS2Class.set_fov, daemon=True).start()

        def setFovValue(id, value):
            novaCS2Class.config["misc"]["fov_changer"]["value"] = value

        def toggleWeaponEsp(id, value):
            novaCS2Class.config["misc"]["weapon_esp"] = value

        def toggleBotIndicator(id, value):
            novaCS2Class.config["misc"]["bot_indicator"] = value

        def toggleBunnyHop(id, value):
            novaCS2Class.config["misc"]["bunny_hop"]["enabled"] = value
            if value and novaCS2Class.bunny_hop_available:
                threading.Thread(target=novaCS2Class.bunny_hop, daemon=True).start()

        waitingForKeyBunnyHop = False
        def statusBindBunnyHop(id):
            global waitingForKeyBunnyHop
            if not waitingForKeyBunnyHop:
                with dpg.handler_registry(tag="BunnyHop Bind Handler"):
                    dpg.add_key_press_handler(callback=setBindBunnyHop)
                dpg.set_item_label(buttonBindBunnyHop, "...")
                waitingForKeyBunnyHop = True

        def setBindBunnyHop(id, value):
            global waitingForKeyBunnyHop
            if waitingForKeyBunnyHop and value != 0:
                novaCS2Class.config["misc"]["bunny_hop"]["bind"] = value
                dpg.set_item_label(buttonBindBunnyHop, f"Bind: {chr(value)}")
                dpg.delete_item("BunnyHop Bind Handler")
                waitingForKeyBunnyHop = False
                print(f"BunnyHop bind set to: {chr(value)}")

        def toggleDiscordRpc(id, value):
            novaCS2Class.config["misc"]["discord_rpc"]["enabled"] = value
            if value and novaCS2Class.discord_rpc_available:
                threading.Thread(target=novaCS2Class.discord_rpc_update, daemon=True).start()

        def toggleFpsOverlay(id, value):
            novaCS2Class.config["misc"]["fps_overlay"]["enabled"] = value
            if value and not novaCS2Class.overlayThreadExists:
                threading.Thread(target=novaCS2Class.overlay, daemon=True).start()

        def toggleSaveSettings(id, value):
            novaCS2Class.config["settings"]["saveSettings"] = value

        def toggleStreamProof(id, value):
            novaCS2Class.config["settings"]["streamProof"] = value
            if value:
                user32.SetWindowDisplayAffinity(novaCS2Class.guiWindowHandle, 0x00000011)
                user32.SetWindowDisplayAffinity(novaCS2Class.overlayWindowHandle, 0x00000011)
            else:
                user32.SetWindowDisplayAffinity(novaCS2Class.guiWindowHandle, 0x00000000)
                user32.SetWindowDisplayAffinity(novaCS2Class.overlayWindowHandle, 0x00000000)

        def toggleAlwaysOnTop(id, value):
            if value:
                win32gui.SetWindowPos(novaCS2Class.guiWindowHandle, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            else:
                win32gui.SetWindowPos(novaCS2Class.guiWindowHandle, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

        def toggleArduino(id, value):
            novaCS2Class.config["arduino"]["enabled"] = value
            if value and novaCS2Class.config["arduino"]["port"]:
                try:
                    novaCS2Class.arduino_serial = serial.Serial(novaCS2Class.config["arduino"]["port"], 9600, timeout=1)
                    print(f"Connected to Arduino on port {novaCS2Class.config['arduino']['port']}")
                except Exception as e:
                    print(f"Failed to connect to Arduino: {e}")
                    novaCS2Class.config["arduino"]["enabled"] = False
                    dpg.set_value(checkboxArduino, False)
            else:
                if novaCS2Class.arduino_serial:
                    novaCS2Class.arduino_serial.close()
                    novaCS2Class.arduino_serial = None
                    print("Arduino connection closed")

        def setArduinoPort(id, value):
            novaCS2Class.config["arduino"]["port"] = value
            if novaCS2Class.config["arduino"]["enabled"] and value:
                try:
                    if novaCS2Class.arduino_serial:
                        novaCS2Class.arduino_serial.close()
                    novaCS2Class.arduino_serial = serial.Serial(value, 9600, timeout=1)
                    print(f"Connected to Arduino on port {value}")
                except Exception as e:
                    print(f"Failed to connect to Arduino: {e}")
                    novaCS2Class.config["arduino"]["enabled"] = False
                    dpg.set_value(checkboxArduino, False)

        def setInputMethod(id, value):
            novaCS2Class.config["arduino"]["input_method"] = value
            if value == "Arduino" and novaCS2Class.config["arduino"]["port"]:
                try:
                    if novaCS2Class.arduino_serial:
                        novaCS2Class.arduino_serial.close()
                    novaCS2Class.arduino_serial = serial.Serial(novaCS2Class.config["arduino"]["port"], 9600, timeout=1)
                    novaCS2Class.config["arduino"]["enabled"] = True
                    dpg.set_value(checkboxArduino, True)
                    print(f"Arduino input method enabled on port {novaCS2Class.config['arduino']['port']}")
                except Exception as e:
                    print(f"Failed to connect to Arduino: {e}")
                    novaCS2Class.config["arduino"]["enabled"] = False
                    dpg.set_value(checkboxArduino, False)
            else:
                if novaCS2Class.arduino_serial:
                    novaCS2Class.arduino_serial.close()
                    novaCS2Class.arduino_serial = None
                    print("Arduino connection closed, switched to Windows input")
                novaCS2Class.config["arduino"]["enabled"] = False
                dpg.set_value(checkboxArduino, False)

        with dpg.window(label=title, width=uiWidth, height=uiHeight, no_collapse=True, no_move=True, no_resize=True, on_close=lambda: os._exit(0)) as window:
            with dpg.tab_bar():
                with dpg.tab(label="ESP"):
                    with dpg.collapsing_header(label="ESP Controls", default_open=True):
                        dpg.add_spacer(height=10)
                        with dpg.group(horizontal=True):
                            checkboxToggleEsp = dpg.add_checkbox(label="Enable ESP", default_value=novaCS2Class.config["esp"]["enabled"], callback=toggleEsp)
                            dpg.add_text("  ")
                            buttonBindEsp = dpg.add_button(label="Click to Bind", callback=statusBindEsp, width=100)
                            bind = novaCS2Class.config["esp"]["bind"]
                            if bind != 0:
                                dpg.set_item_label(buttonBindEsp, f"Bind: {chr(bind)}")
                            with dpg.popup(checkboxToggleEsp, mousebutton=dpg.mvMouseButton_Right, tag="esp_popup"):
                                dpg.add_text("ESP Info")
                                dpg.add_separator()
                                dpg.add_text("Toggles ESP features for player visibility")
                            with dpg.tooltip(checkboxToggleEsp):
                                dpg.add_text("Toggle ESP features on/off")
                            with dpg.tooltip(buttonBindEsp):
                                dpg.add_text("Set a key to toggle ESP")
                        dpg.add_spacer(height=10)
                        dpg.add_separator()

                    with dpg.collapsing_header(label="Visual Settings", default_open=True):
                        dpg.add_spacer(height=10)
                        with dpg.group(horizontal=True):
                            checkboxEspBox = dpg.add_checkbox(label="Box", default_value=novaCS2Class.config["esp"]["box"], callback=toggleEspBox)
                            dpg.add_text("  ")
                            checkboxEspBackground = dpg.add_checkbox(label="Box Background", default_value=novaCS2Class.config["esp"]["boxBackground"], callback=toggleEspBoxBackground)
                            with dpg.tooltip(checkboxEspBox):
                                dpg.add_text("Draw a box around players")
                            with dpg.tooltip(checkboxEspBackground):
                                dpg.add_text("Fill the box with a semi-transparent background")
                        with dpg.group(horizontal=True):
                            checkboxEspSkeleton = dpg.add_checkbox(label="Skeleton", default_value=novaCS2Class.config["esp"]["skeleton"], callback=toggleEspSkeleton)
                            dpg.add_text("  ")
                            checkboxEspRedHead = dpg.add_checkbox(label="Red Head Dot", default_value=novaCS2Class.config["esp"]["redHead"], callback=toggleEspRedHead)
                            with dpg.tooltip(checkboxEspSkeleton):
                                dpg.add_text("Show player skeleton")
                            with dpg.tooltip(checkboxEspRedHead):
                                dpg.add_text("Highlight head with a red dot")
                        checkboxEspSnapline = dpg.add_checkbox(label="Snapline", default_value=novaCS2Class.config["esp"]["snapline"], callback=toggleEspSnapline)
                        with dpg.tooltip(checkboxEspSnapline):
                            dpg.add_text("Draw a line to the player's head")
                        checkboxEspName = dpg.add_checkbox(label="Show Name", default_value=novaCS2Class.config["esp"]["name"], callback=toggleEspName)
                        with dpg.tooltip(checkboxEspName):
                            dpg.add_text("Display player names")
                        checkboxEspHealth = dpg.add_checkbox(label="Show Health", default_value=novaCS2Class.config["esp"]["health"], callback=toggleEspHealth)
                        with dpg.tooltip(checkboxEspHealth):
                            dpg.add_text("Show health bars")
                        checkboxEspDistance = dpg.add_checkbox(label="Show Distance", default_value=novaCS2Class.config["esp"]["distance"], callback=toggleEspDistance)
                        with dpg.tooltip(checkboxEspDistance):
                            dpg.add_text("Show distance to players in meters")
                        dpg.add_spacer(height=10)
                        dpg.add_separator()
                        dpg.add_spacer(height=10)
                        sliderEspBoxRounding = dpg.add_slider_float(label="Box Rounding", default_value=novaCS2Class.config["esp"]["boxRounding"], min_value=0, max_value=1, clamped=True, format="%.1f", callback=setEspBoxRounding, width=300)
                        with dpg.tooltip(sliderEspBoxRounding):
                            dpg.add_text("Adjust the roundness of ESP boxes")

                with dpg.tab(label="TriggerBot"):
                    with dpg.collapsing_header(label="TriggerBot Controls", default_open=True):
                        dpg.add_spacer(height=10)
                        with dpg.group(horizontal=True):
                            checkboxToggleTriggerBot = dpg.add_checkbox(label="Enable TriggerBot", default_value=novaCS2Class.config["triggerBot"]["enabled"], callback=toggleTriggerBot)
                            dpg.add_text("  ")
                            buttonBindTriggerBot = dpg.add_button(label="Click to Bind", callback=statusBindTriggerBot, width=100)
                            bind = novaCS2Class.config["triggerBot"]["bind"]
                            if bind != 0:
                                dpg.set_item_label(buttonBindTriggerBot, f"Bind: {chr(bind)}")
                            with dpg.tooltip(checkboxToggleTriggerBot):
                                dpg.add_text("Enable automatic shooting when aiming at a target")
                            with dpg.tooltip(buttonBindTriggerBot):
                                dpg.add_text("Set a key to activate TriggerBot")
                        dpg.add_spacer(height=10)
                        dpg.add_separator()
                        dpg.add_spacer(height=10)
                        checkboxTriggerBotOnlyEnemies = dpg.add_checkbox(label="Only Enemies", default_value=novaCS2Class.config["triggerBot"]["onlyEnemies"], callback=toggleTriggerBotOnlyEnemies)
                        with dpg.tooltip(checkboxTriggerBotOnlyEnemies):
                            dpg.add_text("Trigger only on enemies")
                        sliderDelayTriggerBot = dpg.add_slider_float(label="Shot Delay (s)", default_value=novaCS2Class.config["triggerBot"]["delay"], max_value=1, callback=sliderTriggerBotDelay, width=300, clamped=True, format="%.2f")
                        with dpg.tooltip(sliderDelayTriggerBot):
                            dpg.add_text("Set delay before shooting")

                with dpg.tab(label="Aimbot"):
                    with dpg.collapsing_header(label="Aimbot Controls", default_open=True):
                        dpg.add_spacer(height=10)
                        checkboxToggleAimbot = dpg.add_checkbox(label="Enable Aimbot (Hold RMB)", default_value=novaCS2Class.config["aimbot"]["enabled"], callback=toggleAimbot)
                        with dpg.tooltip(checkboxToggleAimbot):
                            dpg.add_text("Enable aimbot when holding right mouse button")
                        checkboxAimbotShowFov = dpg.add_checkbox(label="Show FOV Circle", default_value=novaCS2Class.config["aimbot"]["show_fov"], callback=toggleAimbotShowFov)
                        with dpg.tooltip(checkboxAimbotShowFov):
                            dpg.add_text("Display the aimbot's field of view circle")
                        checkboxAimbotWallCheck = dpg.add_checkbox(label="Wall Check", default_value=novaCS2Class.config["aimbot"]["wall_check"], callback=toggleAimbotWallCheck)
                        with dpg.tooltip(checkboxAimbotWallCheck):
                            dpg.add_text("Prevent aiming through walls")
                        checkboxAimbotAntiRecoil = dpg.add_checkbox(label="Anti-Recoil", default_value=novaCS2Class.config["aimbot"]["anti_recoil"], callback=toggleAimbotAntiRecoil, enabled=novaCS2Class.anti_recoil_available)
                        with dpg.tooltip(checkboxAimbotAntiRecoil):
                            dpg.add_text("Compensate for weapon recoil")
                        dpg.add_spacer(height=10)
                        dpg.add_separator()
                        dpg.add_spacer(height=10)
                        sliderAimbotFov = dpg.add_slider_float(label="FOV (degrees)", default_value=novaCS2Class.config["aimbot"]["fov"], min_value=10, max_value=180, clamped=True, format="%.1f", callback=setAimbotFov, width=300)
                        with dpg.tooltip(sliderAimbotFov):
                            dpg.add_text("Set the aimbot's field of view")
                        sliderAimbotSmooth = dpg.add_slider_float(label="Smoothness", default_value=novaCS2Class.config["aimbot"]["smooth"], min_value=0.5, max_value=10, clamped=True, format="%.1f", callback=setAimbotSmooth, width=300)
                        with dpg.tooltip(sliderAimbotSmooth):
                            dpg.add_text("Adjust aimbot smoothness")
                        sliderAimbotSensitivity = dpg.add_slider_float(label="Sensitivity", default_value=novaCS2Class.config["aimbot"]["sensitivity"], min_value=0.1, max_value=5.0, clamped=True, format="%.1f", callback=setAimbotSensitivity, width=300)
                        with dpg.tooltip(sliderAimbotSensitivity):
                            dpg.add_text("Adjust aimbot sensitivity")
                        comboAimbotBone = dpg.add_combo(label="Target Bone", items=["Head", "Neck", "Chest", "Pelvis"], default_value=novaCS2Class.config["aimbot"]["bone_selection"], callback=setAimbotBone, width=300)
                        with dpg.tooltip(comboAimbotBone):
                            dpg.add_text("Select the target bone for aimbot")
                        checkboxAimbotOnlyEnemies = dpg.add_checkbox(label="Only Enemies", default_value=novaCS2Class.config["aimbot"]["onlyEnemies"], callback=toggleAimbotOnlyEnemies)
                        with dpg.tooltip(checkboxAimbotOnlyEnemies):
                            dpg.add_text("Aimbot targets only enemies")

                with dpg.tab(label="Misc"):
                    with dpg.collapsing_header(label="Miscellaneous Settings", default_open=True):
                        dpg.add_spacer(height=10)
                        checkboxNoFlash = dpg.add_checkbox(label="No Flash", default_value=novaCS2Class.config["misc"]["noFlash"], callback=toggleNoFlash)
                        with dpg.tooltip(checkboxNoFlash):
                            dpg.add_text("Disable flashbang effects")
                        checkboxRadar = dpg.add_checkbox(label="Radar", default_value=novaCS2Class.config["misc"]["radar"], callback=toggleRadar)
                        with dpg.tooltip(checkboxRadar):
                            dpg.add_text("Show enemy positions on a mini-radar")
                        checkboxFpsOverlay = dpg.add_checkbox(label="FPS Overlay", default_value=novaCS2Class.config["misc"]["fps_overlay"]["enabled"], callback=toggleFpsOverlay)
                        with dpg.tooltip(checkboxFpsOverlay):
                            dpg.add_text("Show FPS counter in top-left corner")
                        checkboxFovChanger = dpg.add_checkbox(label="FOV Changer", default_value=novaCS2Class.config["misc"]["fov_changer"]["enabled"], callback=toggleFovChanger, enabled=novaCS2Class.fov_changer_available)
                        with dpg.tooltip(checkboxFovChanger):
                            dpg.add_text("Enable custom field of view")
                        sliderFovValue = dpg.add_slider_float(label="FOV Value", default_value=novaCS2Class.config["misc"]["fov_changer"]["value"], min_value=60, max_value=120, clamped=True, format="%.0f", callback=setFovValue, width=300)
                        with dpg.tooltip(sliderFovValue):
                            dpg.add_text("Set custom field of view value")
                        checkboxWeaponEsp = dpg.add_checkbox(label="Weapon ESP", default_value=novaCS2Class.config["misc"]["weapon_esp"], callback=toggleWeaponEsp, enabled=novaCS2Class.weapon_esp_available)
                        with dpg.tooltip(checkboxWeaponEsp):
                            dpg.add_text("Display weapon names in ESP")
                        checkboxBotIndicator = dpg.add_checkbox(label="Bot Indicator", default_value=novaCS2Class.config["misc"]["bot_indicator"], callback=toggleBotIndicator)
                        with dpg.tooltip(checkboxBotIndicator):
                            dpg.add_text("Show whether a player is a bot")
                        with dpg.group(horizontal=True):
                            checkboxBunnyHop = dpg.add_checkbox(label="Bunny Hop", default_value=novaCS2Class.config["misc"]["bunny_hop"]["enabled"], callback=toggleBunnyHop, enabled=novaCS2Class.bunny_hop_available)
                            dpg.add_text("  ")
                            buttonBindBunnyHop = dpg.add_button(label="Click to Bind", callback=statusBindBunnyHop, width=100)
                            bind = novaCS2Class.config["misc"]["bunny_hop"]["bind"]
                            if bind != 0:
                                dpg.set_item_label(buttonBindBunnyHop, f"Bind: {chr(bind)}")
                            with dpg.tooltip(checkboxBunnyHop):
                                dpg.add_text("Enable automatic bunny hopping when holding the bind key")
                            with dpg.tooltip(buttonBindBunnyHop):
                                dpg.add_text("Set a key to activate Bunny Hop")
                        checkboxDiscordRpc = dpg.add_checkbox(label="Discord RPC", default_value=novaCS2Class.config["misc"]["discord_rpc"]["enabled"], callback=toggleDiscordRpc, enabled=novaCS2Class.discord_rpc_available)
                        with dpg.tooltip(checkboxDiscordRpc):
                            dpg.add_text("Show Nova CS2 status on Discord profile")

                with dpg.tab(label="Arduino"):
                    with dpg.collapsing_header(label="Arduino Settings", default_open=True):
                        dpg.add_spacer(height=10)
                        checkboxArduino = dpg.add_checkbox(label="Enable Arduino", default_value=novaCS2Class.config["arduino"]["enabled"], callback=toggleArduino)
                        with dpg.tooltip(checkboxArduino):
                            dpg.add_text("Enable mouse control via Arduino")
                        ports = [port.device for port in serial.tools.list_ports.comports()]
                        comboArduinoPort = dpg.add_combo(label="Arduino Port", items=ports, default_value=novaCS2Class.config["arduino"]["port"], callback=setArduinoPort, width=300)
                        with dpg.tooltip(comboArduinoPort):
                            dpg.add_text("Select the Arduino COM port")
                        comboInputMethod = dpg.add_combo(label="Input Method", items=["Windows", "Arduino"], default_value=novaCS2Class.config["arduino"]["input_method"], callback=setInputMethod, width=300)
                        with dpg.tooltip(comboInputMethod):
                            dpg.add_text("Choose between Windows SendInput or Arduino for mouse control")
                        dpg.add_spacer(height=10)
                        dpg.add_separator()
                        dpg.add_spacer(height=10)

                with dpg.tab(label="Settings"):
                    with dpg.collapsing_header(label="General Settings", default_open=True):
                        dpg.add_spacer(height=10)
                        checkboxSaveSettings = dpg.add_checkbox(label="Save Settings", default_value=novaCS2Class.config["settings"]["saveSettings"], callback=toggleSaveSettings)
                        with dpg.tooltip(checkboxSaveSettings):
                            dpg.add_text("Save configuration to file")
                        checkboxStreamProof = dpg.add_checkbox(label="Stream Proof", default_value=novaCS2Class.config["settings"]["streamProof"], callback=toggleStreamProof)
                        with dpg.tooltip(checkboxStreamProof):
                            dpg.add_text("Hide overlay from screen capture")
                        checkboxAlwaysOnTop = dpg.add_checkbox(label="Always On Top", callback=toggleAlwaysOnTop)
                        with dpg.tooltip(checkboxAlwaysOnTop):
                            dpg.add_text("Keep the UI window on top of others")
                        dpg.add_spacer(height=10)
                        dpg.add_separator()
                        dpg.add_spacer(height=10)

        def dragViewport(sender, appData, userData):
            if dpg.get_mouse_pos(local=False)[1] <= 40:
                dragDeltas = appData
                viewportPos = dpg.get_viewport_pos()
                newX = viewportPos[0] + dragDeltas[1]
                newY = max(viewportPos[1] + dragDeltas[2], 0)
                dpg.set_viewport_pos([newX, newY])

        with dpg.handler_registry():
            dpg.add_mouse_drag_handler(button=0, threshold=0.0, callback=dragViewport)

        with dpg.font_registry():
            with dpg.font("C:\\Windows\\Fonts\\Arial.ttf", 20) as large_font:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
                dpg.bind_font(large_font)

        with dpg.theme() as globalTheme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, Colors.ui_background)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, Colors.dark_purple)
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (255, 255, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (225, 225, 225, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, Colors.dark_purple)
                dpg.add_theme_color(dpg.mvThemeCol_Button, Colors.dark_purple)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 50, 150, 255))
                dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 8)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 8)

        dpg.bind_theme(globalTheme)
        dpg.create_viewport(title=title, width=uiWidth, height=uiHeight, decorated=False, resizable=False)
        dpg.show_viewport()
        novaCS2Class.guiWindowHandle = win32gui.FindWindow(title, None)
        if novaCS2Class.config["settings"]["streamProof"]:
            user32.SetWindowDisplayAffinity(novaCS2Class.guiWindowHandle, 0x00000011)
        dpg.setup_dearpygui()
        dpg.start_dearpygui()
        await asyncio.sleep(0)

    if platform.system() == "Emscripten":
        asyncio.ensure_future(main())
    else:
        asyncio.run(main())