import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import datetime
import asyncio

from myserver import server_on

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())


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
boss_notifications = {}

boss_list = {
    1: "ชั้นล่าง โฮทูร่า (Hotura)",
    2: "ถ้ำ 7 ทิกดัลที่บ้าคลั่ง (Cave 7)",
    3: "ถ้ำ 8 กัทฟิลเลียนชั่วร้าย (Cave 8)",
    4: "ถ้ำ 9 แพนเดอเรปลุกพลัง (Cave 9)",
    5: "พื้นที่ใหม่ 2 ฮาคีร์ (Rcave 2)",
    6: "พื้นที่ใหม่ 3 ดามิโรส (Rcave 3)",
    7: "พื้นที่ใหม่ 4 คาฟคา (Rcave 4)",
    8: "อัศวินแห่งความพินาศ (Ruined Knight)",
    9: "ประกายไฟแห่งการดับสูญ (Tandallon)"
}

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

# ----------- สำหรับบอร์ดแคสต์ข้อความไปยังห้องที่กำหนดไว้  -----------
@bot.tree.command(name='pattern_broadcast', description='บอร์ดแคสต์ข้อความตามแพทเทิร์น')
@app_commands.describe(boss_id="รหัสบอส (1-9)")
@app_commands.describe(date="วันที่ (เช่น 25/10/24)")
@app_commands.describe(time="เวลาบอสเกิด (เช่น 18:00)")

async def pattern_broadcast(interaction: discord.Interaction, boss_id: int, date: str, time: str):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    if boss_id in boss_list:
        boss_name = boss_list[boss_id]
        message = f"# ✦ Boss:{boss_name} Date:{date} Time:{time} ✦"

        guild_id = interaction.guild_id
        if guild_id in broadcast_channels:
            for channel_id in broadcast_channels[guild_id]:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(message)
            await interaction.followup.send("บอร์ดแคสต์ข้อความตามแพทเทิร์นเรียบร้อยแล้ว!", ephemeral=True)
        else:
            await interaction.followup.send("ยังไม่มีห้องที่ตั้งค่าให้บอร์ดแคสต์", ephemeral=True)
    else:
        await interaction.followup.send("รหัสบอสไม่ถูกต้อง โปรดลองใหม่", ephemeral=True)

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
@bot.tree.command(name='boss_set_notification', description='ตั้งค่าแจ้งเตือนบอส')
async def boss_set_notification(interaction: discord.Interaction, boss_id: int, hours: int, minutes: int, owner: str,
                                role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id
    if guild_id not in boss_notifications:
        boss_notifications[guild_id] = []

    now = datetime.datetime.utcnow()
    spawn_time = now + datetime.timedelta(hours=hours, minutes=minutes)
    boss_notifications[guild_id].append({
        "boss_id": boss_id,
        "spawn_time": spawn_time,
        "owner": owner,
        "role": role.id
    })

    await interaction.followup.send(
        f"ตั้งค่าแจ้งเตือนบอส {boss_list[boss_id]} เรียบร้อยแล้ว! จะเกิดในอีก {hours} ชั่วโมง {minutes} นาที.",
        ephemeral=True)
    await schedule_boss_notifications(guild_id, boss_id, spawn_time, role)


async def schedule_boss_notifications(guild_id, boss_id, spawn_time, role):
    now = datetime.datetime.utcnow()
    time_until_spawn = (spawn_time - now).total_seconds()
    time_before_five_min = max(time_until_spawn - 300, 0)

    await asyncio.sleep(time_before_five_min)
    if guild_id in boss_channels:
        channel_id = boss_channels[guild_id]
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(title="แจ้งเตือนล่วงหน้า",
                                  description=f"{role.mention} บอส {boss_list[boss_id]} จะเกิดในอีก 5 นาที!",
                                  color=discord.Color.yellow())
            await channel.send(embed=embed)

    await asyncio.sleep(300)
    if guild_id in boss_channels:
        channel_id = boss_channels[guild_id]
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(title="บอสเกิดแล้ว!",
                                  description=f"{role.mention} บอส {boss_list[boss_id]} เกิดแล้ว!",
                                  color=discord.Color.red())
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
        boss_name = boss_list[notif['boss_id']]
        time_remaining = notif['spawn_time'] - now
        hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        owner = notif['owner']
        embed.add_field(name=f"{idx}. บอส {boss_name}",
                        value=f"เกิดอีก {hours} ชั่วโมง {minutes} นาที ของ {owner}",
                        inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)

server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
