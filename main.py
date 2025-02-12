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
update_log_channels = {}  # {guild_id: channel_id}
guild_active_roles = {}  # {guild_id: {guild_name: role_id}}
broadcast_channels = {}  # ✅
boss_channels = {}  # เก็บค่า channel_id ของแต่ละเซิร์ฟเวอร์ ✅
role_notifications = {}  # เก็บข้อมูล role ที่ใช้แท็กตอนแจ้งเตือนบอส ✅
# Dictionary เก็บค่าห้องที่บอททำงานและคะแนนอิโมจิ
active_rooms = {}  # {guild_id: channel_id}
emoji_bp = {}  # {guild_id: {emoji: point}}
user_scores = {}  # {guild_id: {user_id: score}}
admin_roles = {}  # {guild_id: role_name}

# -------------------------------------------------------
@bot.event
async def on_ready():
    print("Bot Online!")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")


# -------------------------------------------------------

# ----------- ดูที่ตั้งค่าของเซิร์ฟเวอร์ *มีอัพเดท* ✅-----------
@bot.tree.command(name="view_setting", description="ดูการตั้งค่าการแจ้งเตือน")
async def view_setting(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    role_id = boss_roles.get(guild_id)

    role_display = f"<@&{role_id}>" if role_id else "❌ ยังไม่ได้ตั้งค่า"  # ✅
    boss_channel_id = boss_channels.get(guild_id, "❌ ยังไม่ได้ตั้งค่า")  # ✅
    broadcast_channel_id = broadcast_channels.get(guild_id, "❌ ยังไม่ได้ตั้งค่า")  # ✅
    admin_role_name = admin_roles.get(guild_id, "❌ ยังไม่ได้ตั้งค่า")
    update_log_channel_id = update_log_channels.get(guild_id)
    update_log_channel_display = f"<#{update_log_channel_id}>" if update_log_channel_id else "❌ ยังไม่ได้ตั้งค่า"
    active_guilds = guild_active_roles.get(guild_id, {})
    active_guilds_display = "\n".join(
        [f"🔹 {name}: <@&{rid}>" for name, rid in active_guilds.items()]) if active_guilds else "❌ ยังไม่ได้ตั้งค่า"

    embed = discord.Embed(title="🔧 การตั้งค่าของเซิร์ฟเวอร์", color=discord.Color.blue())
    embed.add_field(name="🔔 Role Notification", value=role_display, inline=False)  # ✅
    embed.add_field(name="📢 Boss Notification Channel", value=f"<#{boss_channel_id}>", inline=False)  # ✅
    embed.add_field(name="📡 Broadcast Channel", value=f"[{broadcast_channel_id}]", inline=False)  # ✅
    embed.add_field(name="🛠️ Admin Role", value=admin_role_name, inline=False)
    embed.add_field(name="📝 Update Log Channel", value=update_log_channel_display, inline=False)
    embed.add_field(name="🏰 Active Guilds", value=active_guilds_display, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"[DEBUG] view_setting for guild {guild_id}")


# ----------- กำหนดบอสเป็น Enum ✅-----------
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

    @classmethod
    def from_value(cls, value):
        for boss in cls:
            if boss.value == value:
                return boss
        return None


# ----------- สำหรับเพิ่มห้องเพื่อบอร์ดแคสต์ ✅-----------
@bot.tree.command(name='add_channel', description='เพิ่มห้องบอร์ดแคสต์')
async def add_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    guild_id = interaction.guild_id
    if guild_id not in broadcast_channels:
        broadcast_channels[guild_id] = []

    if channel.id not in broadcast_channels[guild_id]:
        broadcast_channels[guild_id].append(channel.id)
        await interaction.followup.send(f"เพิ่มห้อง {channel.name} เข้าสู่รายการบอร์ดแคสต์เรียบร้อยแล้ว!",
                                        ephemeral=True)
    else:
        await interaction.followup.send(f"ห้อง {channel.name} มีอยู่ในรายการบอร์ดแคสต์อยู่แล้ว", ephemeral=True)


# ----------- สำหรับลบห้องออกจากรายการบอร์ดแคสต์ ✅-----------
@bot.tree.command(name='remove_channel', description='ลบห้องออกจากบอร์ดแคสต์')
async def remove_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    guild_id = interaction.guild_id
    if guild_id in broadcast_channels and channel.id in broadcast_channels[guild_id]:
        broadcast_channels[guild_id].remove(channel.id)
        await interaction.followup.send(f"ลบห้อง {channel.name} ออกจากรายการบอร์ดแคสต์แล้ว", ephemeral=True)
    else:
        await interaction.followup.send(f"ไม่พบห้อง {channel.name} ในรายการบอร์ดแคสต์", ephemeral=True)


# ----------- สำหรับบอร์ดแคสต์ข้อความไปยังห้องที่กำหนดไว้ ✅-----------
@bot.tree.command(name='pattern_broadcast', description='บอร์ดแคสต์ข้อความตามแพทเทิร์น')
@app_commands.describe(
    boss_name="เลือกบอสจากรายการ",
    date="วันที่ (เช่น 25/10/24)",
    time="เวลาบอสเกิด (เช่น 18:00)"
)
async def pattern_broadcast(interaction: discord.Interaction, boss_name: BossName, date: str, time: str):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer

    boss_display_name = boss_name.value  # ✅ ไม่ต้อง replace แล้ว
    message = f"### ✦～ 𝐁𝐨𝐬𝐬﹕{boss_display_name} 𝐃𝐚𝐭𝐞﹕{date} {time} ～✦"

    guild_id = interaction.guild_id
    if guild_id in broadcast_channels:
        for channel_id in broadcast_channels[guild_id]:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(message)
        await interaction.followup.send("บอร์ดแคสต์ข้อความตามแพทเทิร์นเรียบร้อยแล้ว!", ephemeral=True)
    else:
        await interaction.followup.send("ยังไม่มีห้องที่ตั้งค่าให้บอร์ดแคสต์", ephemeral=True)


# ----------- ปุ่มยืนยัน/ยกเลิกสำหรับ set_boss_channel -----------
class ConfirmView(View):
    def __init__(self, interaction, channel):
        super().__init__()
        self.interaction = interaction
        self.channel = channel

    @discord.ui.button(label="ยืนยัน", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        guild_id = self.interaction.guild_id
        boss_channels[guild_id] = self.channel.id
        await self.interaction.followup.send(f"ตั้งค่าช่อง {self.channel.name} เป็นช่องแจ้งเตือนบอสเรียบร้อยแล้ว!",
                                             ephemeral=True)
        self.stop()

    @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await self.interaction.followup.send("ยกเลิกการตั้งค่าช่องแจ้งเตือนบอส", ephemeral=True)
        self.stop()


# ----------- ระบบตั้งค่าห้องแจ้งเตือนเวลาบอส ✅ -----------
@bot.tree.command(name='set_boss_channel', description='ตั้งค่าช่องสำหรับแจ้งเตือนบอส')
async def set_boss_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild_id  # ✅ ดึง ID ของเซิร์ฟเวอร์
    boss_channels[guild_id] = channel.id  # ✅ บันทึกค่า channel.id ตาม guild
    # ✅ ตอบกลับโดยตรง แทนการ defer()
    await interaction.response.send_message(
        f"✅ ตั้งค่าช่อง {channel.mention} เป็นช่องแจ้งเตือนบอสเรียบร้อยแล้ว!", ephemeral=True
    )


# ----------- ตั้งค่า Role ที่ต้องการให้บอทแท็กในการแจ้งเตือนบอส ✅-----------
@bot.tree.command(name="set_role_notification", description="ตั้งค่า Role สำหรับแจ้งเตือนบอส")
async def set_role_notification(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild_id
    boss_roles[guild_id] = role.id  # บันทึก role.id ลง dictionary

    await interaction.response.send_message(
        f"✅ ตั้งค่า Role Notification เป็น <@&{role.id}> เรียบร้อยแล้ว!",
        ephemeral=True
    )

    print(f"[DEBUG] boss_roles: {boss_roles}")


# ----------- คำสั่งแจ้งเตือนเวลาบอส ✅-----------
class OwnerType(Enum):
    KNIGHT = "knight"
    BISHOP = "bishop"


@tree.command(name='boss_set_notification', description='ตั้งค่าแจ้งเตือนบอส')
async def boss_set_notification(
        interaction: discord.Interaction,
        boss_name: BossName,
        hours: int,
        minutes: int,
        owner: OwnerType,
        role: discord.Role = None  # ทำให้ role เป็น optional
):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id

    # ใช้ role ที่ตั้งค่าไว้ ถ้าไม่มีให้ใช้ที่ส่งมา
    if role is None:
        role_id = boss_roles.get(guild_id)
        if role_id:
            role = interaction.guild.get_role(role_id)

    if role is None:  # ถ้ายังไม่มี role ให้แจ้งเตือน
        return await interaction.followup.send("❌ ยังไม่ได้ตั้งค่า Role สำหรับแจ้งเตือนบอส!", ephemeral=True)

    now = datetime.datetime.now(local_tz)  # ✅ ใช้ timezone ที่กำหนด
    spawn_time = now + datetime.timedelta(hours=hours, minutes=minutes)

    if guild_id not in boss_notifications:
        boss_notifications[guild_id] = []

    boss_notifications[guild_id].append({
        "boss_name": boss_name.name,
        "spawn_time": spawn_time,
        "owner": owner.value,
        "role": role.id  # ใช้ role ที่ดึงมา
    })

    await interaction.followup.send(
        f"ตั้งค่าแจ้งเตือนบอส {boss_name.value} เรียบร้อยแล้ว! จะเกิดในอีก {hours} ชั่วโมง {minutes} นาที.",
        ephemeral=True
    )

    await schedule_boss_notifications(guild_id, boss_name.name, spawn_time, owner.value, role)


# ----------- ระบบแจ้งเตือนเวลาบอส ✅-----------
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


local_tz = pytz.timezone("Asia/Bangkok")  # ตั้งเวลาเป็นไทย


# ----------- คำสั่งดูรายการบอสที่ตั้งค่าไว้ ✅-----------
@bot.tree.command(name="boss_notification_list", description="ดูรายการบอสที่ตั้งค่าแจ้งเตือน")
async def boss_notification_list(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)  # ลดดีเลย์จากการ defer

    guild_id = interaction.guild_id
    if guild_id not in boss_notifications or not boss_notifications[guild_id]:
        return await interaction.followup.send("❌ ไม่มีบอสที่ถูกตั้งค่าแจ้งเตือน", ephemeral=True)

    now = datetime.datetime.now(local_tz)

    # กรองรายการบอสที่ยังไม่เกิด
    valid_notifications = [
        notif for notif in boss_notifications[guild_id]
        if notif["spawn_time"] > now
    ]

    if not valid_notifications:
        return await interaction.followup.send("❌ ไม่มีบอสที่ถูกตั้งค่าแจ้งเตือน", ephemeral=True)

    sorted_notifications = sorted(valid_notifications, key=lambda x: x["spawn_time"])

    embed = discord.Embed(title="📜 𝐁𝐨𝐬𝐬 𝐒𝐩𝐚𝐰𝐧 𝐋𝐢𝐬𝐭", color=discord.Color.blue())

    for idx, notif in enumerate(sorted_notifications[:10], start=1):  # จำกัดสูงสุด 10 รายการ
        boss_name = notif["boss_name"].replace("_", " ")
        spawn_time = notif["spawn_time"].astimezone(local_tz).strftime("%H:%M")
        owner = notif["owner"]
        embed.add_field(name=f"{idx}. 𝐁𝐨𝐬𝐬 ﹕{boss_name} 𝐎𝐰𝐧𝐞𝐫 ﹕{owner}",
                        value=f"𝐒𝐩𝐚𝐰𝐧 ﹕{spawn_time}",
                        inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)

    # ✅ ปุ่ม "ประกาศ"
    class ConfirmView(discord.ui.View):
        def __init__(self, embed):
            super().__init__(timeout=60)
            self.embed = embed  # ✅ เก็บ Embed ไว้ใช้ในปุ่ม

        @discord.ui.button(label="📢 ประกาศ", style=discord.ButtonStyle.green)
        async def announce(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()

            guild_id = interaction.guild_id
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

    await interaction.followup.send(embed=embed, ephemeral=True, view=ConfirmView(embed))  # ✅ ส่ง Embed ไปพร้อมปุ่ม


# -------------------- คำสั่งทั้งหมดข้างบนใช้งานได้แล้ว --------------------

# 🔹 รายชื่ออาชีพที่เลือกได้
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


# ----------- ตั้งค่าช่องและ Role -----------
update_log_channel_id = None  # เก็บ ID ห้อง update log
admin_role_name = "Admin"  # ชื่อ Role แอดมิน


# ----------- ห้องสำหรับบันทึกอัพเดต -----------
@bot.tree.command(name="set_update_log_channel", description="ตั้งค่าห้อง update log")
async def set_update_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild_id
    update_log_channels[guild_id] = channel.id  # ✅ แก้ไขให้ใช้ dictionary ที่ถูกต้อง
    await interaction.response.send_message(f"✅ ตั้งค่าห้อง update log เป็น {channel.mention} เรียบร้อย",
                                            ephemeral=True)


# ----------- ตั้งค่ายศแอดมิน -----------
@bot.tree.command(name="set_admin_role", description="ตั้งค่า Role แอดมิน")
async def set_admin_role(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild_id
    admin_roles[guild_id] = role.name  # เก็บ Role แอดมินตามเซิร์ฟเวอร์

    await interaction.response.send_message(f"✅ ตั้งค่า Role แอดมินเป็น {role.mention} สำหรับเซิร์ฟเวอร์นี้",
                                            ephemeral=True)


# ----------- ตั้งค่ายศกิลด์ที่ใช้งาน -----------
@bot.tree.command(name="set_guild_active", description="ตั้งค่า Role ของกิลด์ที่ใช้งาน")
async def set_guild_active(interaction: discord.Interaction, guild_name: str, role: discord.Role):
    guild_id = interaction.guild_id

    if guild_id not in guild_active_roles:
        guild_active_roles[guild_id] = {}

    guild_active_roles[guild_id][guild_name] = role.id  # ✅ บันทึกค่าของ Role ไว้ใน Dictionary
    await interaction.response.send_message(
        f"✅ ตั้งค่า Role **{role.name}** สำหรับกิลด์ **{guild_name}** แล้ว!",
        ephemeral=True
    )


# ----------- ลบยศที่กิลด์ที่ใช้งาน -----------
@bot.tree.command(name="remove_guild_active", description="Remove a guild from active selection")
async def remove_guild_active(interaction: discord.Interaction, guild_name: str):
    if guild_name in guild_role_manager.guild_roles:
        guild_role_manager.remove_guild_role(guild_name)
        await interaction.response.send_message(f"✅ ลบกิลด์ที่ไม่ใช้งานออกแล้ว: {guild_name}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ ไม่มีกิลด์ที่ต้องการลบ.", ephemeral=True)
# -----------
def is_admin(member):
    """ตรวจสอบว่าเป็นแอดมินหรือไม่"""
    guild_id = member.guild.id
    admin_role = admin_roles.get(guild_id)
    return admin_role and discord.utils.get(member.roles, name=admin_role)


@bot.tree.command(name='set_emoji_bp', description='จัดการคะแนนอิโมจิ')
@app_commands.choices(action=[
    app_commands.Choice(name='ตั้งค่า', value='set'),
    app_commands.Choice(name='แก้ไข', value='edit'),
    app_commands.Choice(name='ลบ', value='delete')
])
async def set_emoji_bp(interaction: discord.Interaction, action: app_commands.Choice[str], emoji: str,
                       points: int = None):
    guild_id = interaction.guild_id
    if guild_id not in emoji_bp:
        emoji_bp[guild_id] = {}

    if action.value == 'set' or action.value == 'edit':
        if points is None:
            return await interaction.response.send_message('❌ โปรดระบุคะแนน BP', ephemeral=True)
        emoji_bp[guild_id][emoji] = points
        await interaction.response.send_message(f'✅ ตั้งค่าอิโมจิ {emoji} ให้มีค่า {points} BP แล้ว!', ephemeral=True)
    elif action.value == 'delete':
        if emoji in emoji_bp[guild_id]:
            del emoji_bp[guild_id][emoji]
            await interaction.response.send_message(f'✅ ลบอิโมจิ {emoji} ออกจากระบบเรียบร้อยแล้ว!', ephemeral=True)
        else:
            await interaction.response.send_message(f'❌ ไม่พบอิโมจิ {emoji} ในระบบ', ephemeral=True)


@bot.tree.command(name='check_bp', description='ดูคะแนน BP')
@app_commands.choices(option=[
    app_commands.Choice(name='เช็ครายคน', value='individual'),
    app_commands.Choice(name='เช็คทั้งหมด', value='all')
])
async def check_bp(interaction: discord.Interaction, option: app_commands.Choice[str], member: discord.Member = None):
    guild_id = interaction.guild_id
    if guild_id not in user_scores:
        return await interaction.response.send_message('❌ ยังไม่มีการบันทึกคะแนน BP', ephemeral=True)

    if option.value == 'individual':
        if member:
            score = user_scores[guild_id].get(member.id, 0)
            await interaction.response.send_message(f'🔹 {member.mention} มี {score} BP', ephemeral=True)
        else:
            await interaction.response.send_message('❌ โปรดระบุสมาชิกที่ต้องการเช็คคะแนน BP', ephemeral=True)
    elif option.value == 'all':
        scores = sorted(user_scores[guild_id].items(), key=lambda x: x[1], reverse=True)
        leaderboard = '\n'.join([f'<@{user_id}>: {score} BP' for user_id, score in scores])
        embed = discord.Embed(title='📜 Leaderboard BP', description=leaderboard, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='add_bp', description='เพิ่มคะแนน BP ให้สมาชิก')
async def add_bp(interaction: discord.Interaction, member: discord.Member, points: int):
    guild_id = interaction.guild_id
    if guild_id not in user_scores:
        user_scores[guild_id] = {}
    if member.id not in user_scores[guild_id]:
        user_scores[guild_id][member.id] = 0
    user_scores[guild_id][member.id] += points
    await interaction.response.send_message(f'✅ เพิ่ม {points} BP ให้ {member.mention} แล้ว!', ephemeral=True)


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
    
server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
