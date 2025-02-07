import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import datetime
import asyncio
import pytz

from myserver import server_on
from enum import Enum

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
tree = bot.tree
local_tz = pytz.timezone('Asia/Bangkok')  # ใช้เวลาประเทศไทย
# ตัวแปรเก็บข้อมูลบอสแจ้งเตือน
boss_notifications = {}  # {guild_id: [{"boss_name": "..", "spawn_time": datetime, "owner": ".."}]}
boss_roles = {}  # {guild_id: role_id}  # สำหรับแท็ก Role ที่ต้องการตอนกดประกาศ

@bot.event
async def on_ready():
    print("Bot Online!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")


broadcast_channels = {}
boss_channels = {}  # เก็บค่า channel_id ของแต่ละเซิร์ฟเวอร์
boss_notifications = {}  # เก็บข้อมูลแจ้งเตือนบอส
role_notifications = {} # ก็บข้อมูล role ที่ใช้แท็กตอนแจ้งเตือนบอส

# ----------- ดูี่ตั้งค่า -----------
@bot.tree.command(name="view_setting", description="ดูการตั้งค่าทั้งหมดในเซิร์ฟเวอร์")
async def view_setting(interaction: discord.Interaction):
    guild_id = interaction.guild_id  # ✅ ดึง ID ของเซิร์ฟเวอร์

    # ✅ ดึงค่าการตั้งค่า (ถ้าไม่มีให้แสดง 'ยังไม่ได้ตั้งค่า')
    role_notification = role_notifications.get(guild_id, "❌ ยังไม่ได้ตั้งค่า")
    boss_channel = boss_channels.get(guild_id, "❌ ยังไม่ได้ตั้งค่า")
    broadcast_channel = broadcast_channels.get(guild_id, "❌ ยังไม่ได้ตั้งค่า")

    # ✅ ตอบกลับ Embed สวยงาม
    embed = discord.Embed(title="🔧 การตั้งค่าของเซิร์ฟเวอร์", color=discord.Color.blue())
    embed.add_field(name="🔔 Role Notification",
                    value=f"<@&{role_notification}>" if isinstance(role_notification, int) else role_notification,
                    inline=False)
    embed.add_field(name="📢 Boss Notification Channel",
                    value=f"<#{boss_channel}>" if isinstance(boss_channel, int) else boss_channel, inline=False)
    embed.add_field(name="📡 Broadcast Channel",
                    value=f"<#{broadcast_channel}>" if isinstance(broadcast_channel, int) else broadcast_channel,
                    inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ----------- กำหนดบอสเป็น Enum -----------
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

    @classmethod
    def from_value(cls, value):
        for boss in cls:
            if boss.value == value:
                return boss
        return None

# ----------- สำหรับเพิ่มห้องเพื่อบอร์ดแคสต์ -----------
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


# ----------- สำหรับลบห้องออกจากรายการบอร์ดแคสต์ -----------
@bot.tree.command(name='remove_channel', description='ลบห้องออกจากบอร์ดแคสต์')
async def remove_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    guild_id = interaction.guild_id
    if guild_id in broadcast_channels and channel.id in broadcast_channels[guild_id]:
        broadcast_channels[guild_id].remove(channel.id)
        await interaction.followup.send(f"ลบห้อง {channel.name} ออกจากรายการบอร์ดแคสต์แล้ว", ephemeral=True)
    else:
        await interaction.followup.send(f"ไม่พบห้อง {channel.name} ในรายการบอร์ดแคสต์", ephemeral=True)


# ----------- สำหรับบอร์ดแคสต์ข้อความไปยังห้องที่กำหนดไว้ -----------
@bot.tree.command(name='pattern_broadcast', description='บอร์ดแคสต์ข้อความตามแพทเทิร์น')
@app_commands.describe(
    boss_name="เลือกบอสจากรายการ",
    date="วันที่ (เช่น 25/10/24)",
    time="เวลาบอสเกิด (เช่น 18:00)"
)

async def pattern_broadcast(interaction: discord.Interaction, boss_name: BossName, date: str, time: str):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer

    boss_display_name = boss_name.value  # ✅ ไม่ต้อง replace แล้ว
    message = f"## ✦～ 𝐁𝐨𝐬𝐬﹕{boss_display_name} 𝐃𝐚𝐭𝐞﹕{date} {time} ～✦"

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

# ----------- ระบบตั้งค่าห้องแจ้งเตือนเวลาบอส  -----------
@bot.tree.command(name='set_boss_channel', description='ตั้งค่าช่องสำหรับแจ้งเตือนบอส')
async def set_boss_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild_id  # ✅ ดึง ID ของเซิร์ฟเวอร์
    boss_channels[guild_id] = channel.id  # ✅ บันทึกค่า channel.id ตาม guild
    # ✅ ตอบกลับโดยตรง แทนการ defer()
    await interaction.response.send_message(
        f"✅ ตั้งค่าช่อง {channel.mention} เป็นช่องแจ้งเตือนบอสเรียบร้อยแล้ว!", ephemeral=True
    )

# ----------- ตั้งค่า Role ที่ต้องการให้บอทแท็กในการแจ้งเตือนบอส -----------
@bot.tree.command(name="set_role_notification", description="ตั้งค่า Role ที่ต้องการให้บอทแท็กในการแจ้งเตือนบอส")
@app_commands.describe(role="เลือก Role ที่ต้องการให้แท็ก")
async def set_role_notification(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild_id
    boss_roles[guild_id] = role.id  # บันทึก Role ID
    await interaction.response.send_message(f"✅ ตั้งค่า Role สำหรับแจ้งเตือนบอสเป็น {role.mention} แล้ว!", ephemeral=True)

# ----------- ระบบแจ้งเตือนเวลาบอส -----------
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
        role: discord.Role
):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id
    if guild_id not in boss_notifications:
        boss_notifications[guild_id] = []

    now = datetime.datetime.now(local_tz)  # ✅ ใช้ timezone ที่กำหนด
    spawn_time = now + datetime.timedelta(hours=hours, minutes=minutes)

    boss_notifications[guild_id].append({
        "boss_name": boss_name.name,  # เก็บ key ของ Enum เช่น "CAVE_7"
        "spawn_time": spawn_time,
        "owner": owner.value,
        "role": role.id
    })

    await interaction.followup.send(
        f"ตั้งค่าแจ้งเตือนบอส {boss_name.value} เรียบร้อยแล้ว! จะเกิดในอีก {hours} ชั่วโมง {minutes} นาที.",
        ephemeral=True
    )

    await schedule_boss_notifications(guild_id, boss_name.name, spawn_time, owner.value, role)


async def schedule_boss_notifications(guild_id, boss_name, spawn_time, owner, role):
    # ฟังก์ชันจัดการแจ้งเตือนบอส (ยังไม่แก้ไข แต่ต้องเปลี่ยน boss_id → boss_name)
    pass

async def schedule_boss_notifications(guild_id, boss_name, spawn_time, owner, role):
    now = datetime.datetime.utcnow()
    time_until_spawn = (spawn_time - now).total_seconds()
    time_before_five_min = max(time_until_spawn - 300, 0)
    owner_icon = "💙" if owner == "knight" else "💚"

    boss_display_name = BossName[boss_name].value  # แปลงให้ชื่อดูดีขึ้น

    await asyncio.sleep(time_before_five_min)
    if guild_id in boss_channels:
        channel_id = boss_channels[guild_id]
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="𝐁𝐨𝐬𝐬 𝐍𝐨𝐭𝐢𝐟𝐢𝐜𝐚𝐭𝐢𝐨𝐧!!",
                description=f"{owner_icon} 𝐁𝐨𝐬𝐬 {boss_display_name} 𝐢𝐬 𝐬𝐩𝐚𝐰𝐧𝐢𝐧𝐠 𝐢𝐧 𝟓 𝐦𝐢𝐧𝐮𝐭𝐞𝐬! {role.mention}",
                color=discord.Color.yellow()
            )
            await channel.send(embed=embed)

    await asyncio.sleep(300)  # รอจนถึงเวลาบอสเกิด
    if guild_id in boss_channels:
        channel_id = boss_channels[guild_id]
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="𝐁𝐨𝐬𝐬 𝐡𝐚𝐬 𝐬𝐩𝐚𝐰𝐧!!",
                description=f"{owner_icon} 𝐁𝐨𝐬𝐬 {boss_display_name} 𝐡𝐚𝐬 𝐒𝐩𝐚𝐰𝐧 𝐋𝐞𝐭'𝐬 𝐟𝐢𝐠𝐡𝐭! {role.mention}",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

local_tz = pytz.timezone("Asia/Bangkok")  # ตั้งเวลาเป็นไทย

# ----------- คำสั่งดูรายการบอสที่ตั้งค่าไว้ -----------
@bot.tree.command(name="boss_notification_list", description="ดูรายการบอสที่ตั้งค่าแจ้งเตือน")
async def boss_notification_list(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # ✅ ป้องกัน timeout
    guild_id = interaction.guild_id

    # ✅ ตรวจสอบว่ามีการแจ้งเตือนบอสไหม
    if guild_id not in boss_notifications or not boss_notifications[guild_id]:
        return await interaction.followup.send("❌ ไม่มีบอสที่ถูกตั้งค่าแจ้งเตือน", ephemeral=True)

    now = datetime.datetime.utcnow()

    # ✅ สร้างสำเนา list เพื่อป้องกันปัญหาลบข้อมูลโดยตรง
    valid_notifications = [notif for notif in boss_notifications[guild_id] if notif["spawn_time"] > now]

    if not valid_notifications:  # ถ้าลบแล้วไม่มีบอสเหลือ
        return await interaction.followup.send("❌ ไม่มีบอสที่ถูกตั้งค่าแจ้งเตือน", ephemeral=True)

    # ✅ เรียงลำดับตามเวลาสปอน
    sorted_notifications = sorted(valid_notifications, key=lambda x: x["spawn_time"])

    embed = discord.Embed(title="📜 รายการแจ้งเตือนบอส", color=discord.Color.blue())

    for idx, notif in enumerate(sorted_notifications, start=1):
        boss_name = notif["boss_name"].replace("_", " ")
        spawn_time = notif["spawn_time"].astimezone(local_tz).strftime("%H:%M")  # ✅ ตรวจสอบ local_tz
        owner = notif["owner"]
        embed.add_field(name=f"{idx}. 𝐁𝐨𝐬𝐬 ﹕{boss_name} 𝐎𝐰𝐧𝐞𝐫 ﹕{owner}",
                        value=f"𝐒𝐩𝐚𝐰𝐧 ﹕{spawn_time} (𝗨𝗧𝗖 +𝟳)",
                        inline=False)

    # ✅ ปุ่ม "ประกาศ" หรือ "ปิด"
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

            await channel.send(f"{role_mention} 📢 **อัปเดตรายการบอส!**", embed=self.embed)
            await interaction.followup.send("✅ ประกาศไปที่ห้องแจ้งเตือนเรียบร้อย!", ephemeral=True)

        @discord.ui.button(label="❌ ปิด", style=discord.ButtonStyle.red)
        async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await interaction.followup.send("✅ ปิดการดูรายการแจ้งเตือน", ephemeral=True)

    await interaction.followup.send(embed=embed, ephemeral=True, view=ConfirmView(embed))  # ✅ ส่ง Embed ไปพร้อมปุ่ม

server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
