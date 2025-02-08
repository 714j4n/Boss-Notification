import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import datetime
import asyncio
import pytz

from discord.ui import Modal, Select, TextInput, View
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
broadcast_channels = {} # ✅
boss_channels = {}  # เก็บค่า channel_id ของแต่ละเซิร์ฟเวอร์ ✅
role_notifications = {} # เก็บข้อมูล role ที่ใช้แท็กตอนแจ้งเตือนบอส ✅

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

    role_display = f"<@&{role_id}>" if role_id else "❌ ยังไม่ได้ตั้งค่า" # ✅
    boss_channel_id = boss_channels.get(guild_id, "❌ ยังไม่ได้ตั้งค่า") # ✅
    broadcast_channel_id = broadcast_channels.get(guild_id, "❌ ยังไม่ได้ตั้งค่า") # ✅
    admin_role_name = admin_roles.get(guild_id, "❌ ยังไม่ได้ตั้งค่า")
    update_log_channel_id = update_log_channels.get(guild_id)
    update_log_channel_display = f"<#{update_log_channel_id}>" if update_log_channel_id else "❌ ยังไม่ได้ตั้งค่า"
    active_guilds = guild_active_roles.get(guild_id, {})
    active_guilds_display = "\n".join([f"🔹 {name}: <@&{rid}>" for name, rid in active_guilds.items()]) if active_guilds else "❌ ยังไม่ได้ตั้งค่า"

    embed = discord.Embed(title="🔧 การตั้งค่าของเซิร์ฟเวอร์", color=discord.Color.blue())
    embed.add_field(name="🔔 Role Notification", value=role_display, inline=False) # ✅
    embed.add_field(name="📢 Boss Notification Channel", value=f"<#{boss_channel_id}>", inline=False) # ✅
    embed.add_field(name="📡 Broadcast Channel", value=f"[{broadcast_channel_id}]", inline=False) # ✅
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

    if time_before_five_min > 0: # รอ 5 นาทีก่อนบอสเกิด
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
        title="🛠️ อัพเดทข้อมูลของคุณ",
        description="เลือกประเภทการอัพเดทข้อมูลที่คุณต้องการด้านล่าง:\n"
                    "- อัพเดทชื่อ\n"
                    "- อัพเดทอาชีพ\n"
                    "- อัพเดทกิลด์\n\n"
                    "กดที่ปุ่มเพื่อดำเนินการต่อ",
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
        self.add_item(UpdateButton("อัพเดทชื่อ", "name"))
        self.add_item(UpdateButton("อัพเดทอาชีพ", "job"))
        self.add_item(UpdateButton("อัพเดทกิลด์", "guild"))


class UpdateButton(discord.ui.Button):
    def __init__(self, label, update_type):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.update_type = update_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(UpdateModal(self.update_type))


class UpdateModal(discord.ui.Modal, title="กรอกข้อมูลสำหรับอัพเดท"):
    def __init__(self, update_type):
        super().__init__()
        self.update_type = update_type
        self.member_id = discord.ui.TextInput(label="เลขสมาชิก (5 หลัก)", required=True, max_length=5)
        self.old_data = discord.ui.TextInput(label="ข้อมูลเดิม", required=True)
        self.new_data = discord.ui.TextInput(label="ข้อมูลใหม่", required=True)
        self.add_item(self.member_id)
        self.add_item(self.old_data)
        self.add_item(self.new_data)

    async def on_submit(self, interaction: discord.Interaction):
        # Embed สำหรับห้อง update log
        embed = discord.Embed(
            title="📝 คำขออัพเดทข้อมูล",
            description=f"ประเภท: {self.update_type}\n"
                        f"เลขสมาชิก: {self.member_id.value}\n"
                        f"ข้อมูลเดิม: {self.old_data.value}\n"
                        f"ข้อมูลใหม่: {self.new_data.value}",
            color=discord.Color.yellow(),
        )
        embed.set_footer(text="รอการยืนยันจากแอดมิน")

        # ปุ่มสำหรับยืนยัน/ยกเลิก
        view = AdminConfirmView(update_type=self.update_type, modal_data={
            "member_id": self.member_id.value,
            "old_data": self.old_data.value,
            "new_data": self.new_data.value,
        })

        # ส่ง Embed ไปที่ห้อง update log
        log_channel = interaction.guild.get_channel(update_log_channel_id)
        await log_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ คำขออัพเดทข้อมูลถูกส่งแล้ว", ephemeral=True)

# ----------- ยืนยัน/ยกเลิกคำขอ -----------
class AdminConfirmView(discord.ui.View):
    def __init__(self, update_type, modal_data):
        super().__init__(timeout=None)
        self.update_type = update_type
        self.modal_data = modal_data
        self.add_item(AdminConfirmButton("ยืนยัน", True, self.update_type, self.modal_data))
        self.add_item(AdminConfirmButton("ยกเลิก", False, self.update_type, self.modal_data))


class AdminConfirmButton(discord.ui.Button):
    def __init__(self, label, confirm, update_type, modal_data):
        style = discord.ButtonStyle.success if confirm else discord.ButtonStyle.danger
        super().__init__(label=label, style=style)
        self.confirm = confirm
        self.update_type = update_type
        self.modal_data = modal_data

    async def callback(self, interaction: discord.Interaction):
        if "Admin" not in [role.name for role in interaction.user.roles]:
            await interaction.response.send_message("❌ คุณไม่มีสิทธิ์กดปุ่มนี้", ephemeral=True)
            return

        if self.confirm:
            # ดำเนินการตามประเภท
            if self.update_type == "name":
                member = interaction.guild.get_member_named(f"{self.modal_data['member_id']} - {self.modal_data['old_data']}")
                if member:
                    await member.edit(nick=f"{self.modal_data['member_id']} - {self.modal_data['new_data']}")
                    await interaction.message.edit(content="✅ ชื่อถูกอัพเดทเรียบร้อย", view=None)

            elif self.update_type == "guild":
                member = interaction.guild.get_member_named(f"{self.modal_data['member_id']} - {self.modal_data['old_data']}")
                if member:
                    old_role = discord.utils.get(interaction.guild.roles, name=self.modal_data['old_data'])
                    new_role = discord.utils.get(interaction.guild.roles, name=self.modal_data['new_data'])
                    if old_role:
                        await member.remove_roles(old_role)
                    if new_role:
                        await member.add_roles(new_role)
                    await interaction.message.edit(content="✅ กิลด์ถูกอัพเดทเรียบร้อย", view=None)

        else:
            await interaction.message.edit(content="❌ คำขอถูกยกเลิก", view=None)

# ----------- ตั้งค่าช่องและ Role -----------
update_log_channel_id = None  # เก็บ ID ห้อง update log
admin_role_name = "Admin"  # ชื่อ Role แอดมิน

@bot.tree.command(name="set_update_log_channel", description="ตั้งค่าห้อง update log")
async def set_update_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    global update_log_channel_id
    update_log_channel_id = channel.id
    await interaction.response.send_message(f"✅ ตั้งค่าห้อง update log เป็น {channel.mention} เรียบร้อย", ephemeral=True)
# -----------
@bot.tree.command(name="set_admin_role", description="ตั้งค่า Role แอดมิน")
async def set_admin_role(interaction: discord.Interaction, role: discord.Role):
    global admin_role_name
    admin_role_name = role.name
    await interaction.response.send_message(f"✅ ตั้งค่า Role แอดมินเป็น {role.mention} เรียบร้อย", ephemeral=True)

# ----------- ห้องสำหรับโพสต์ให้กดอัพเดต -----------
@bot.tree.command(name="update_info_post", description="ตั้งค่าโพสต์สำหรับอัพเดทข้อมูล")
async def update_info_post(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple()
    )
    view = UpdateInfoView(interaction.guild_id)
    await interaction.response.send_message(embed=embed, view=view)

# ----------- ห้องสำหรับบันทึกอัพเดต -----------
@bot.tree.command(name="set_update_log_channel", description="ตั้งค่าห้องดูประวัติการอัพเดท")
async def set_update_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild_id
    update_log_channels[guild_id] = channel.id  # ✅ บันทึกค่า ID ของห้องอัพเดท
    await interaction.response.send_message(f"✅ ตั้งค่าห้องอัพเดทเป็น {channel.mention}", ephemeral=True)

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

# ----------- ตั้งค่ายศแอดมิน -----------
@bot.tree.command(name="set_admin_role", description="ตั้งยศเป็นแอดมินเพื่อเช็คอัพเดท")
async def set_admin_role(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild_id
    admin_roles[guild_id] = role.name

    await interaction.response.send_message(f"✅ ตั้ง {role.name} เป็นแอดมินในเซิร์ฟเวอร์นี้แล้ว", ephemeral=True)

server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
