import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, Select, TextInput

import datetime
import asyncio
import pytz

from myserver import server_on
from enum import Enum

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
tree = bot.tree
local_tz = pytz.timezone('Asia/Bangkok')  # ใช้เวลาประเทศไทย
# ตัวแปรเก็บข้อมูลบอสแจ้งเตือน + เก็บค่าที่ตั้งค่าไว้สำหรับหลายเซิร์ฟเวอร์
boss_notifications = {}  # {guild_id: [{"boss_name": "..", "spawn_time": datetime, "owner": ".."}]} ✅
boss_roles = {}  # {guild_id: role_id}  # สำหรับแท็ก Role ที่ต้องการตอนกดประกาศ ✅
admin_roles = {}  # {guild_id: role_name}
update_log_channels = {}  # {guild_id: channel_id}
guild_active_roles = {}  # {guild_id: {guild_name: role_id}}
broadcast_channels = {}  # ✅
boss_channels = {}  # เก็บค่า channel_id ของแต่ละเซิร์ฟเวอร์ ✅
role_notifications = {}  # เก็บข้อมูล role ที่ใช้แท็กตอนแจ้งเตือนบอส ✅
# Dictionary เก็บค่าห้องที่บอททำงานและคะแนนอิโมจิ
active_rooms = {}  # {guild_id: channel_id}
emoji_bp = {}  # {guild_id: {emoji: point}}
user_scores = {}  # {guild_id: {user_id: score}}

# -------------------------------------------------------
@bot.event
async def on_ready():
    print("Bot Online!")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# --------------------------------------------------

# ----------- BossName(Enum) ✅-----------
class BossName(Enum):
    HOTURA = "Lower Cave"
    CAVE_7 = "Cave 7"
    CAVE_8 = "Cave 8"
    CAVE_9 = "Cave 9"
    RCAVE_2 = "Rcave 2"
    RCAVE_3 = "Rcave 3"
    RCAVE_4 = "Rcave 4"
    RUINED_KNIGHT = "Ruined Knight"
    TANDALLON = "Tandallon"
    DEFGIO = "Dergio"

# ----------- รายชื่อ Owner -----------
class OwnerType(Enum):
    KNIGHT = "knight"
    BISHOP = "bishop"

    @classmethod
    def from_value(cls, value):
        for boss in cls:
            if boss.value == value:
                return boss
        return None

# ----------- รายชื่ออาชีพที่เลือกได้ -----------
class JobChoicesEnum(discord.Enum):
    SNIPER = "Sniper"
    CLERIC = "Cleric"
    MAGE = "Mage"
    ASSASSIN = "Assassin"
    IMPALER = "Impaler"
    KNIGHT = "Knight"
    GENERAL = "General"
    SLAYER = "Slayer"

class GuildRoleManager:
    def __init__(self):
        self.guild_roles = {}

    def set_guild_roles(self, roles):
        self.guild_roles = roles

    def remove_guild_role(self, guild_name):
        if guild_name in self.guild_roles:
            del self.guild_roles[guild_name]

    def get_role_id(self, guild_name):
        return self.guild_roles.get(guild_name)

guild_role_manager = GuildRoleManager()
admin_role_name = None  # Initially unset
update_log_channel_id = None  # Initially unset

#----------- setroom -----------
@bot.tree.command(name="setroom", description="ตั้งค่าห้องสำหรับบอท เช่น ห้องบอส อัปเดต และบอร์ดแคสต์")
@app_commands.choices(
    room_type=[
        app_commands.Choice(name="ห้องแจ้งเตือนบอส", value="boss_channel"),
        app_commands.Choice(name="ห้องอัปเดตข้อมูล", value="update_log"),
        app_commands.Choice(name="ห้องบอททำงาน", value="active_room"),
        app_commands.Choice(name="ห้องบอร์ดแคสต์", value="broadcast"),
    ],
    action=[
        app_commands.Choice(name="ตั้งค่า", value="set"),
        app_commands.Choice(name="แก้ไข", value="edit"),
        app_commands.Choice(name="ลบ", value="remove"),
        app_commands.Choice(name="ดูห้องที่ตั้งค่า", value="view"),
    ]
)
async def setroom(interaction: discord.Interaction, room_type: app_commands.Choice[str],
                  action: app_commands.Choice[str], channel: discord.TextChannel = None):
    guild_id = interaction.guild_id

    # คำสั่งดูห้องที่ตั้งค่า
    if action.value == "view":
        room_dict = {
            "boss_channel": boss_channels,
            "update_log": update_log_channels,
            "active_room": active_rooms,
            "broadcast": broadcast_channels
        }
        room_id = room_dict.get(room_type.value, {}).get(guild_id)
        if room_id:
            room = bot.get_channel(room_id)
            room_mention = room.mention if room else f"❌ ห้องไม่พบ (ID: {room_id})"
            await interaction.response.send_message(f"🔹 ห้องที่ตั้งค่าอยู่: {room_mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ ยังไม่มีการตั้งค่าห้อง {room_type.name}", ephemeral=True)
        return

    # ต้องระบุห้องเมื่อใช้ set/edit/remove
    if not channel and action.value in ["set", "edit", "remove"]:
        return await interaction.response.send_message("❌ โปรดระบุห้องที่ต้องการตั้งค่า", ephemeral=True)

    # ตั้งค่าห้อง
    if action.value == "set":
        if room_type.value == "broadcast":
            if guild_id not in broadcast_channels:
                broadcast_channels[guild_id] = []
            broadcast_channels[guild_id].append(channel.id)
        else:
            room_dict = {
                "boss_channel": boss_channels,
                "update_log": update_log_channels,
                "active_room": active_rooms,
            }
            room_dict[room_type.value][guild_id] = channel.id

        await interaction.response.send_message(
            f"✅ ตั้งค่าห้อง {channel.mention} สำหรับ {room_type.name} เรียบร้อยแล้ว!", ephemeral=True)

    # แก้ไขห้อง (เหมือนกับ set)
    elif action.value == "edit":
        if room_type.value == "broadcast":
            return await interaction.response.send_message(
                "❌ ไม่สามารถแก้ไขห้องบอร์ดแคสต์ได้ โปรดใช้ `remove` แล้ว `set` ใหม่", ephemeral=True)

        room_dict = {
            "boss_channel": boss_channels,
            "update_log": update_log_channels,
            "active_room": active_rooms,
        }
        room_dict[room_type.value][guild_id] = channel.id

        await interaction.response.send_message(
            f"✅ เปลี่ยนห้องเป็น {channel.mention} สำหรับ {room_type.name} เรียบร้อยแล้ว!", ephemeral=True)

    # ลบห้องออกจากระบบ
    elif action.value == "remove":
        if room_type.value == "broadcast":
            if guild_id in broadcast_channels and channel.id in broadcast_channels[guild_id]:
                broadcast_channels[guild_id].remove(channel.id)
                await interaction.response.send_message(f"✅ ลบห้อง {channel.mention} ออกจากบอร์ดแคสต์แล้ว!",
                                                        ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ ไม่พบห้อง {channel.mention} ในบอร์ดแคสต์!", ephemeral=True)
        else:
            room_dict = {
                "boss_channel": boss_channels,
                "update_log": update_log_channels,
                "active_room": active_rooms,
            }
            if guild_id in room_dict[room_type.value]:
                del room_dict[room_type.value][guild_id]
                await interaction.response.send_message(f"✅ ลบการตั้งค่าห้อง {room_type.name} เรียบร้อยแล้ว!",
                                                        ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ ยังไม่มีห้อง {room_type.name} ที่ตั้งค่าไว้",
                                                        ephemeral=True)
#----------- setrole -----------
@bot.tree.command(name="setrole", description="ตั้งค่า Role สำหรับบอท เช่น Role บอส, แอดมิน และกิลด์")
@app_commands.choices(
    role_type=[
        app_commands.Choice(name="Role แจ้งเตือนบอส", value="boss_role"),
        app_commands.Choice(name="Role แอดมิน", value="admin_role"),
        app_commands.Choice(name="Role ของกิลด์", value="guild_role"),
    ],
    action=[
        app_commands.Choice(name="ตั้งค่า", value="set"),
        app_commands.Choice(name="แก้ไข", value="edit"),
        app_commands.Choice(name="ลบ", value="remove"),
        app_commands.Choice(name="ดูการตั้งค่า", value="view"),
    ]
)
async def setrole(
    interaction: discord.Interaction,
    role_type: app_commands.Choice[str],
    action: app_commands.Choice[str],
    role: discord.Role = None,
    guild_name: str = None
):
    guild_id = interaction.guild_id

    # ---------------------- ดูการตั้งค่า ----------------------
    if action.value == "view":
        role_dict = {
            "boss_role": boss_roles,
            "admin_role": admin_roles,
            "guild_role": guild_active_roles
        }
        if role_type.value == "guild_role":
            roles_info = "\n".join([f"🔹 {g_name}: <@&{r_id}>" for g_name, r_id in role_dict["guild_role"].get(guild_id, {}).items()])
            response = roles_info if roles_info else "❌ ยังไม่มีการตั้งค่า Role กิลด์"
        else:
            role_id = role_dict[role_type.value].get(guild_id)
            response = f"🔹 Role ที่ตั้งค่า: <@&{role_id}>" if role_id else f"❌ ยังไม่มีการตั้งค่า {role_type.name}"
        return await interaction.response.send_message(response, ephemeral=True)

    # ---------------------- ตรวจสอบ input ----------------------
    if not role and action.value in ["set", "edit", "remove"]:
        return await interaction.response.send_message("❌ โปรดระบุ Role ที่ต้องการตั้งค่า", ephemeral=True)

    if role_type.value == "guild_role" and not guild_name:
        return await interaction.response.send_message("❌ โปรดระบุชื่อกิลด์สำหรับ Role กิลด์", ephemeral=True)

    # ---------------------- ตั้งค่า Role ----------------------
    if action.value == "set":
        if role_type.value == "guild_role":
            if guild_id not in guild_active_roles:
                guild_active_roles[guild_id] = {}
            guild_active_roles[guild_id][guild_name] = role.id
        else:
            role_dict = {
                "boss_role": boss_roles,
                "admin_role": admin_roles
            }
            role_dict[role_type.value][guild_id] = role.id

        await interaction.response.send_message(f"✅ ตั้งค่า {role.mention} เป็น {role_type.name} เรียบร้อยแล้ว!", ephemeral=True)

    # ---------------------- แก้ไข Role (เหมือนกับ set) ----------------------
    elif action.value == "edit":
        if role_type.value == "guild_role":
            if guild_id in guild_active_roles and guild_name in guild_active_roles[guild_id]:
                guild_active_roles[guild_id][guild_name] = role.id
            else:
                return await interaction.response.send_message("❌ ไม่พบ Role กิลด์ที่ต้องการแก้ไข", ephemeral=True)
        else:
            role_dict = {
                "boss_role": boss_roles,
                "admin_role": admin_roles
            }
            role_dict[role_type.value][guild_id] = role.id

        await interaction.response.send_message(f"✅ เปลี่ยน {role_type.name} เป็น {role.mention} แล้ว!", ephemeral=True)

    # ---------------------- ลบ Role ----------------------
    elif action.value == "remove":
        if role_type.value == "guild_role":
            if guild_id in guild_active_roles and guild_name in guild_active_roles[guild_id]:
                del guild_active_roles[guild_id][guild_name]
                await interaction.response.send_message(f"✅ ลบ Role ของกิลด์ **{guild_name}** เรียบร้อยแล้ว!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ ไม่พบ Role กิลด์ที่ต้องการลบ", ephemeral=True)
        else:
            role_dict = {
                "boss_role": boss_roles,
                "admin_role": admin_roles
            }
            if guild_id in role_dict[role_type.value]:
                del role_dict[role_type.value][guild_id]
                await interaction.response.send_message(f"✅ ลบการตั้งค่า {role_type.name} เรียบร้อยแล้ว!", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ ยังไม่มี Role {role_type.name} ที่ตั้งค่าไว้", ephemeral=True)

#----------- boss -----------
@bot.tree.command(name="boss", description="ตั้งค่าแจ้งเตือนบอส หรือบอร์ดแคสต์บอส")
@app_commands.choices(
    boss_action=[
        app_commands.Choice(name="ตั้งค่าแจ้งเตือนบอส", value="notification"),
        app_commands.Choice(name="บอร์ดแคสต์บอส", value="broadcast"),
    ],
    sub_action=[
        app_commands.Choice(name="ดูรายการแจ้งเตือน", value="list"),
        app_commands.Choice(name="แก้ไขแจ้งเตือน", value="edit"),
        app_commands.Choice(name="ลบแจ้งเตือน", value="remove"),
    ]
)
async def boss(
        interaction: discord.Interaction,
        boss_action: app_commands.Choice[str],
        sub_action: app_commands.Choice[str] = None,
        boss_name: BossName = None,
        hours: int = None,
        minutes: int = None,
        owner: OwnerType = None,
        date: str = None,
        time: str = None
):
    guild_id = interaction.guild_id

    # ---------------------- คำสั่งแจ้งเตือนบอส ----------------------
    if boss_action.value == "notification" and not sub_action:
        await interaction.response.defer(thinking=True)  # แจ้ง Discord ว่าบอทกำลังประมวลผล

        now = datetime.datetime.now(local_tz)
        spawn_time = now + datetime.timedelta(hours=hours, minutes=minutes)  # คำนวณ spawn_time

        # ตรวจสอบ dictionary เพื่อป้องกัน KeyError
        if guild_id not in boss_notifications:
            boss_notifications[guild_id] = []

        boss_notifications[guild_id].append({
            "boss_name": boss_name.name,
            "spawn_time": spawn_time,
            "owner": owner.value
        })

        role = boss_roles.get(guild_id)
        role_mention = f"<@&{role}>" if role else "@everyone"

        await interaction.followup.send(f"✅ ตั้งค่าแจ้งเตือนบอส {boss_name.value} เวลา {hours} ชั่วโมง {minutes} นาที!",
                                        ephemeral=True)

        # ใช้ asyncio.create_task() เพื่อไม่ให้บอทค้าง
        asyncio.create_task(schedule_boss_notifications(guild_id, boss_name.name, spawn_time, owner.value, role))

        # 1️⃣ ดูรายการแจ้งเตือนบอส (⚡ พร้อมปุ่ม "📢 ประกาศ")
        if sub_action and sub_action.value == "list":
            await interaction.response.defer(thinking=True)
            if guild_id not in boss_notifications or not boss_notifications[guild_id]:
                return await interaction.followup.send("❌ ไม่มีบอสที่ถูกตั้งค่าแจ้งเตือน", ephemeral=True)

            now = datetime.datetime.now(local_tz)
            valid_notifications = [
                notif for notif in boss_notifications[guild_id] if notif["spawn_time"] > now
            ]

            if not valid_notifications:
                return await interaction.followup.send("❌ ไม่มีบอสที่ถูกตั้งค่าแจ้งเตือน", ephemeral=True)

            sorted_notifications = sorted(valid_notifications, key=lambda x: x["spawn_time"])
            embed = discord.Embed(title="📜 𝐁𝐨𝐬𝐬 𝐒𝐩𝐚𝐰𝐧 𝐋𝐢𝐬𝐭", color=discord.Color.blue())

            for idx, notif in enumerate(sorted_notifications[:10], start=1):  # จำกัด 10 รายการ
                boss_name = notif["boss_name"].replace("_", " ")
                spawn_time = notif["spawn_time"].astimezone(local_tz).strftime("%H:%M")
                owner = notif["owner"]
                embed.add_field(name=f"{idx}. 𝐁𝐨𝐬𝐬 ﹕{boss_name} 𝐎𝐰𝐧𝐞𝐫 ﹕{owner}",
                                value=f"𝐒𝐩𝐚𝐰𝐧 ﹕{spawn_time}",
                                inline=False)

            # ✅ ปุ่ม "📢 ประกาศ"
            class ConfirmView(discord.ui.View):
                def __init__(self, embed):
                    super().__init__(timeout=60)
                    self.embed = embed

                @discord.ui.button(label="📢 ประกาศ", style=discord.ButtonStyle.green)
                async def announce(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer()

                    channel_id = boss_channels.get(guild_id)
                    if not channel_id:
                        return await interaction.followup.send("❌ ยังไม่ได้ตั้งค่าช่องแจ้งเตือนบอส!", ephemeral=True)

                    channel = interaction.guild.get_channel(channel_id)
                    if not channel:
                        return await interaction.followup.send("❌ ไม่พบช่องแจ้งเตือน!", ephemeral=True)

                    # ✅ ดึง Role ที่ต้องแท็ก
                    role_id = boss_roles.get(guild_id)
                    role_mention = f"<@&{role_id}>" if role_id else "@everyone"

                    await channel.send(f"📢 **【𝐓𝐢𝐦𝐞 𝐢𝐧 𝐠𝐚𝐦𝐞 + 𝟏𝐡𝐫】** {role_mention}", embed=self.embed)
                    await interaction.followup.send("✅ ประกาศไปที่ห้องแจ้งเตือนเรียบร้อย!", ephemeral=True)

            await interaction.followup.send(embed=embed, ephemeral=True, view=ConfirmView(embed))

        # 2️⃣ แก้ไขรายการแจ้งเตือนบอส
        elif sub_action and sub_action.value == "edit":
            if not boss_name or hours is None or minutes is None:
                return await interaction.response.send_message("❌ โปรดเลือกบอสและเวลาที่ต้องการแก้ไข", ephemeral=True)

            now = datetime.datetime.now(local_tz)
            spawn_time = now + datetime.timedelta(hours=hours, minutes=minutes)

            if guild_id in boss_notifications:
                for notif in boss_notifications[guild_id]:
                    if notif["boss_name"] == boss_name.name:
                        notif["spawn_time"] = spawn_time
                        await schedule_boss_notifications(guild_id, boss_name.name, spawn_time, notif["owner"],
                                                          notif["role"])
                        break
                else:
                    return await interaction.response.send_message("❌ ไม่พบบอสที่ต้องการแก้ไข", ephemeral=True)

            await interaction.response.send_message(
                f"✅ แก้ไขเวลาบอส {boss_name.value} เป็น {hours} ชั่วโมง {minutes} นาที!", ephemeral=True)

        # 3️⃣ ลบรายการแจ้งเตือนบอส
        elif sub_action and sub_action.value == "remove":
            if not boss_name:
                return await interaction.response.send_message("❌ โปรดเลือกบอสที่ต้องการลบ", ephemeral=True)

            if guild_id in boss_notifications:
                boss_notifications[guild_id] = [
                    notif for notif in boss_notifications[guild_id] if notif["boss_name"] != boss_name.name
                ]

            await interaction.response.send_message(f"✅ ลบบอส {boss_name.value} ออกจากรายการแจ้งเตือน!", ephemeral=True)

    # ---------------------- คำสั่งบอร์ดแคสต์บอส ----------------------
    elif boss_action.value == "broadcast":
        if not boss_name or not date or not time:
            return await interaction.response.send_message("❌ โปรดกรอกข้อมูลให้ครบถ้วน!", ephemeral=True)

        message = f"### ✦～ 𝐁𝐨𝐬𝐬﹕{boss_name.value} 𝐃𝐚𝐭𝐞﹕{date} {time} ～✦"

        if guild_id in broadcast_channels:
            for channel_id in broadcast_channels[guild_id]:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(message)
            await interaction.response.send_message("✅ บอร์ดแคสต์ข้อความสำเร็จ!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ยังไม่มีห้องที่ตั้งค่าให้บอร์ดแคสต์!", ephemeral=True)

#----------- schedule boss notifications -----------
async def schedule_boss_notifications(guild_id, boss_name, spawn_time, owner, role):
    now = datetime.datetime.now(local_tz)

    # กรองรายการบอสที่ยังไม่เกิด
    valid_notifications = [
        notif for notif in boss_notifications[guild_id]
        if notif["spawn_time"] > now
    ]

    time_until_spawn = (spawn_time - now).total_seconds()
    time_before_five_min = max(time_until_spawn - 300, 0)
    owner_icon = "💙" if owner == "knight" else "💚"

    boss_display_name = BossName[boss_name].value

    print(f"[DEBUG] Scheduling boss: {boss_name} at {spawn_time} (in {time_until_spawn}s)")

    if time_before_five_min > 0:  # รอ 5 นาทีก่อนบอสเกิด
        await asyncio.sleep(time_before_five_min)

    if guild_id in boss_channels:
        channel_id = boss_channels[guild_id]
        channel = bot.get_channel(channel_id) or bot.get_channel(int(channel_id))
        if channel:
            embed = discord.Embed(
                title="𝐁𝐨𝐬𝐬 𝐍𝐨𝐭𝐢𝐟𝐢𝐜𝐚𝐭𝐢𝐨𝐧!!",
                description=f"{owner_icon} 𝐁𝐨𝐬𝐬 {boss_display_name} 𝐢𝐬 𝐬𝐩𝐚𝐰𝐧𝐢𝐧𝐠 𝐢𝐧 𝟓 𝐦𝐢𝐧𝐮𝐭𝐞𝐬! <@&{role.id}>",
                color=discord.Color.yellow()
            )
            await channel.send(embed=embed)

    await asyncio.sleep(300)  # รอจนถึงเวลาบอสเกิด
    if guild_id in boss_channels:
        channel_id = boss_channels[guild_id]
        channel = bot.get_channel(channel_id) or bot.get_channel(int(channel_id))
        if channel:
            embed = discord.Embed(
                title="𝐁𝐨𝐬𝐬 𝐡𝐚𝐬 𝐬𝐩𝐚𝐰𝐧!!",
                description=f"{owner_icon} 𝐁𝐨𝐬𝐬 {boss_display_name} 𝐡𝐚𝐬 𝐒𝐩𝐚𝐰𝐧 𝐋𝐞𝐭'𝐬 𝐟𝐢𝐠𝐡𝐭! <@&{role.id}>",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

# -------------------- คำสั่งทั้งหมดข้างบนใช้งานได้แล้ว 1--------------------

# ----------- ระบบอัพเดทข้อมูล ชื่อ/อาชีพ/กิลด์ -----------
# ----------- สร้างโพสต์update -----------
@bot.tree.command(name="update_info_post", description="สร้างโพสต์สำหรับอัพเดทข้อมูล")
async def update_info_post(interaction: discord.Interaction, channel: discord.TextChannel):
    # สร้างข้อความ Embed สำหรับโพสต์
    embed = discord.Embed(
        title="✿ เลือกประเภทข้อมูลที่ต้องการอัพเดทข้างล่าง.",
        description="╰ 𝐂𝐡𝐨𝐨𝐬𝐞 𝐭𝐡𝐞 𝐮𝐩𝐝𝐚𝐭𝐞 𝐭𝐲𝐩𝐞 𝐛𝐞𝐥𝐨𝐰.\n\n"
                    "โน้ต﹕  เลขสมาชิก และ ชื่อกิลด์ต้องกรอกให้ถูกต้อง\n"
                    "Note﹕Member ID and Guild Name must be correct.\n"
                    "╰・ eMystic │ zMystic │ โฮ่งโฮ่ง (Woof)",
        color=discord.Color.blue(),
    )
    # สร้าง View พร้อมปุ่ม
    view = UpdateInfoView()

    # ส่งข้อความพร้อมปุ่มไปยังช่องที่เลือก
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ โพสต์สำหรับอัพเดทข้อมูลถูกสร้างใน {channel.mention}", ephemeral=True)

# ----------- สร้างโพสต์ด้วยปุ่ม -----------
class UpdateInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(UpdateButton("𝐍𝐚𝐦𝐞", "name"))
        self.add_item(UpdateButton("𝐉𝐨𝐛", "job"))
        self.add_item(UpdateButton("𝐆𝐮𝐢𝐥𝐝", "guild"))

class UpdateButton(discord.ui.Button):
    def __init__(self, label, update_type):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.update_type = update_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(UpdateModal(self.update_type))

class UpdateModal(discord.ui.Modal, title="𝐔𝐩𝐝𝐚𝐭𝐞 𝐅𝐨𝐫𝐦"):
    def __init__(self, update_type):
        super().__init__()
        self.update_type = update_type
        self.member_id = discord.ui.TextInput(label="𝐌𝐞𝐦𝐛𝐞𝐫 𝐧𝐮𝐦𝐛𝐞𝐫", required=True, max_length=5)
        self.old_data = discord.ui.TextInput(label="𝐎𝐥𝐝 𝐃𝐚𝐭𝐚", required=True)
        self.new_data = discord.ui.TextInput(label="𝐍𝐞𝐰 𝐃𝐚𝐭𝐚", required=True)
        self.add_item(self.member_id)
        self.add_item(self.old_data)
        self.add_item(self.new_data)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        log_channel_id = update_log_channels.get(guild_id)
        # ✅ ดึงข้อมูลผู้ใช้
        user = interaction.user  # ผู้ใช้ที่ส่งฟอร์ม
        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url  # รูปโปรไฟล์

        # ✅ ดึงวันเวลาปัจจุบันเป็น Asia/Bangkok
        now = datetime.datetime.now(local_tz)
        formatted_date = now.strftime("%d/%m/%Y %H:%M")  # แปลงวันที่เป็น DD/MM/YYYY HH:MM

        # ✅ ตรวจสอบห้อง update log
        log_channel = bot.get_channel(log_channel_id) if log_channel_id else None
        if not log_channel:
            return await interaction.response.send_message("❌ ไม่พบห้อง Update Log หรือยังไม่ได้ตั้งค่า!",
                                                           ephemeral=True)

        # ✅ ตรวจสอบและดึงข้อมูล `member`
        member = interaction.guild.get_member(interaction.user.id)
        if not member:
            try:
                member = await bot.fetch_user(interaction.user.id)
            except discord.NotFound:
                return await interaction.response.send_message("❌ ไม่พบข้อมูลสมาชิก!", ephemeral=True)

        if not member:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลสมาชิก!", ephemeral=True)

        # ✅ สร้าง Embed แจ้งเตือนอัปเดต
        embed = discord.Embed(
            title="📝 𝐃𝐚𝐭𝐚 𝐮𝐩𝐝𝐚𝐭𝐞",
            description=f"• 𝐭𝐲𝐩𝐞\n"
                        f"╰  {self.update_type}\n"
                        f"• 𝐦𝐞𝐦𝐛𝐞𝐫 𝐧𝐮𝐦𝐛𝐞𝐫{self.member_id.value}\n"
                        f"╰  {self.member_id.value}\n"
                        f"• 𝐨𝐥𝐝 𝐝𝐚𝐭𝐚 ▸ 𝐧𝐞𝐰 𝐝𝐚𝐭𝐚\n"
                        f"╰  {self.old_data.value} ▸ {self.new_data.value}",
            color=discord.Color.yellow(),
        )
        embed.set_thumbnail(url=avatar_url)  # ✅ เพิ่มรูปโปรไฟล์ของผู้กรอกฟอร์ม
        embed.set_footer(text=f"ID: {user.id}")

        # ✅ ตรวจสอบการเปลี่ยนกิลด์
        if self.update_type == "guild":
            old_guild = self.old_data.value
            new_guild = self.new_data.value

            old_role_id = guild_active_roles.get(guild_id, {}).get(old_guild)
            new_role_id = guild_active_roles.get(guild_id, {}).get(new_guild)

            old_role = interaction.guild.get_role(old_role_id) if old_role_id else None
            new_role = interaction.guild.get_role(new_role_id) if new_role_id else None

            if old_role and old_role in member.roles:
                await member.remove_roles(old_role)
            if new_role:
                await member.add_roles(new_role)

            embed.add_field(name="📌 𝐓𝐫𝐚𝐧𝐬𝐟𝐞𝐫 𝐠𝐮𝐢𝐥𝐝", value=f"𝐌𝐨𝐯𝐞 𝐟𝐫𝐨𝐦 {old_guild} 𝐓𝐨 {new_guild}", inline=False)

        # ✅ ตรวจสอบการเปลี่ยนชื่อ
        elif self.update_type == "name":
            current_nickname = member.display_name
            if " - " in current_nickname:
                member_id, _ = current_nickname.split(" - ", 1)  # แยกเลขสมาชิกออกจากชื่อ
                new_nickname = f"{member_id} - {self.new_data.value}"[:32]  # ใช้เลขสมาชิกเดิม
            else:
                new_nickname = self.new_data.value[:32]  # ถ้าไม่มีเลขสมาชิก ให้ใช้ชื่อใหม่ตรงๆ

            await member.edit(nick=new_nickname)
            embed.add_field(name="📌 𝐂𝐡𝐚𝐧𝐠𝐞 𝐧𝐚𝐦𝐞", value=f"𝐂𝐡𝐚𝐧𝐠𝐞 𝐭𝐨 {self.new_data.value}", inline=False)

        # ✅ บันทึกลง Update Log และแจ้งเตือนสมาชิก
        await log_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ **{self.update_type}** 𝐔𝐩𝐝𝐚𝐭𝐞𝐝!!", ephemeral=True)

# ------------------------------------------------------- ยังไม่ได้เทส ระบบให้คะแนน
def is_admin(member):
    """ตรวจสอบว่าเป็นแอดมินหรือไม่"""
    guild_id = member.guild.id
    admin_role = admin_roles.get(guild_id)
    return admin_role and discord.utils.get(member.roles, name=admin_role)

@bot.tree.command(name="set_admin_role", description="ตั้งค่า Role แอดมิน")
async def set_admin_role(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild_id
    admin_roles[guild_id] = role.name  # เก็บ Role แอดมินตามเซิร์ฟเวอร์
    await interaction.response.send_message(f"✅ ตั้งค่า Role แอดมินเป็น {role.mention} สำหรับเซิร์ฟเวอร์นี้", ephemeral=True)

    @bot.tree.command(name='set_room_active', description='จัดการห้องที่บอททำงาน')
    @app_commands.choices(action=[
        app_commands.Choice(name='ตั้งค่า', value='set'),
        app_commands.Choice(name='แก้ไข', value='edit'),
        app_commands.Choice(name='ดูห้องที่ตั้งค่า', value='view')
    ])
    async def set_room_active(interaction: discord.Interaction, action: app_commands.Choice[str],
                              channel: discord.TextChannel = None):
        guild_id = interaction.guild_id

        if action.value == 'set':
            if not channel:
                return await interaction.response.send_message('❌ โปรดระบุห้องที่ต้องการตั้งค่า', ephemeral=True)
            active_rooms[guild_id] = channel.id
            await interaction.response.send_message(f'✅ ตั้งค่าห้อง {channel.mention} ให้บอททำงานแล้ว!', ephemeral=True)

        elif action.value == 'edit':
            if not channel:
                return await interaction.response.send_message('❌ โปรดระบุห้องใหม่ที่ต้องการตั้งค่า', ephemeral=True)
            if guild_id in active_rooms:
                del active_rooms[guild_id]  # ลบห้องเดิม
            active_rooms[guild_id] = channel.id  # ตั้งค่าห้องใหม่
            await interaction.response.send_message(f'✅ เปลี่ยนห้องเป็น {channel.mention} เรียบร้อยแล้ว!',
                                                    ephemeral=True)

        elif action.value == 'view':
            if guild_id in active_rooms:
                room = bot.get_channel(active_rooms[guild_id])
                room_mention = room.mention if room else '❌ ไม่พบห้อง'
                await interaction.response.send_message(f'🔹 ห้องที่ตั้งค่าอยู่: {room_mention}', ephemeral=True)
            else:
                await interaction.response.send_message('❌ ยังไม่มีการตั้งค่าห้อง', ephemeral=True)

    @bot.event
    async def on_reaction_add(reaction, user):
        if user.bot:
            return  # ข้ามบอท

        message = reaction.message
        guild_id = message.guild.id
        if guild_id not in active_rooms or message.channel.id != active_rooms[guild_id]:
            return  # ไม่ใช่ห้องที่กำหนด

        if guild_id not in admin_roles:
            return  # ถ้ายังไม่มี Role แอดมินที่ตั้งค่าไว้ ไม่ให้ทำงาน

        if not is_admin(user):
            return  # เฉพาะแอดมินเท่านั้น

        emoji = str(reaction.emoji)
        if emoji not in emoji_bp.get(guild_id, {}):
            return  # ไม่ใช่อิโมจิที่กำหนดไว้

        points = emoji_bp[guild_id][emoji]
        user_id = message.author.id
        if guild_id not in user_scores:
            user_scores[guild_id] = {}
        if user_id not in user_scores[guild_id]:
            user_scores[guild_id][user_id] = 0

        user_scores[guild_id][user_id] += points
# -------------------------------------------------------
server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
