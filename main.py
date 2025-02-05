import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import datetime
import asyncio

from myserver import server_on
from enum import Enum

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
tree = bot.tree

@bot.event
async def on_ready():
    print("Bot Online!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")


broadcast_channels = {}
boss_channels = {}
boss_notifications = {}  # เก็บข้อมูลแจ้งเตือนบอส



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

    boss_display_name = boss_name.value.replace("_", " ")  # แปลงชื่อให้อ่านง่าย
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
    await interaction.response.defer(ephemeral=True)
    view = ConfirmView(interaction, channel)
    await interaction.followup.send(f"คุณต้องการตั้งค่าช่อง {channel.name} เป็นช่องแจ้งเตือนบอสหรือไม่?", view=view,
                                    ephemeral=True)


# ----------- ระบบแจ้งเตือนเวลาบอส -----------
from discord import app_commands


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

    now = datetime.datetime.utcnow()
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

# ----------- คำสั่งดูรายการบอสที่ตั้งค่าไว้ -----------
@bot.tree.command(name='boss_notification_list', description='ดูรายการบอสที่ตั้งค่าแจ้งเตือน')
async def boss_notification_list(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id

    if guild_id not in boss_notifications or not boss_notifications[guild_id]:
        await interaction.followup.send("ไม่มีบอสที่ถูกตั้งค่าแจ้งเตือน", ephemeral=True)
        return

    now = datetime.datetime.utcnow()
    sorted_notifications = sorted(boss_notifications[guild_id], key=lambda x: x['spawn_time'])

    embed = discord.Embed(title="📜 รายการแจ้งเตือนบอส", color=discord.Color.blue())

    for idx, notif in enumerate(sorted_notifications, start=1):
        boss_name = notif['boss_name'].replace("_", " ")  # เปลี่ยน _ เป็นช่องว่าง
        spawn_time = notif['spawn_time'].strftime("%H:%M")  # แปลงเวลาที่บอสจะเกิดเป็นรูปแบบ HH:MM
        owner = notif['owner']
        embed.add_field(name=f"{idx}. 𝐁𝐨𝐬𝐬 ﹕{boss_name}",
                        value=f"𝐒𝐩𝐚𝐰𝐧 ﹕{spawn_time} 𝐎𝐰𝐧𝐞𝐫 ﹕{owner}",
                        inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)

server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
