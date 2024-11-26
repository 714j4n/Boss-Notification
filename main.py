import os
import discord
from discord.ext import commands
from discord import app_commands

from myserver import server_on

# กำหนด prefix ของคำสั่ง
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())


# คำสั่งตอบสนองเมื่อบอทออนไลน์
@bot.event
async def on_ready():
    print("Bot Online!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# สร้าง dictionary เพื่อเก็บ ID ของห้องที่จะบอร์ดแคสต์
broadcast_channels = {}


# คำสั่ง slash สำหรับเพิ่มห้องเพื่อบอร์ดแคสต์
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


# คำสั่ง slash สำหรับลบห้องออกจากรายการบอร์ดแคสต์
@bot.tree.command(name='remove_channel', description='ลบห้องออกจากบอร์ดแคสต์')
async def remove_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    guild_id = interaction.guild_id
    if guild_id in broadcast_channels and channel.id in broadcast_channels[guild_id]:
        broadcast_channels[guild_id].remove(channel.id)
        await interaction.followup.send(f"ลบห้อง {channel.name} ออกจากรายการบอร์ดแคสต์แล้ว", ephemeral=True)
    else:
        await interaction.followup.send(f"ไม่พบห้อง {channel.name} ในรายการบอร์ดแคสต์", ephemeral=True)


# คำสั่ง slash สำหรับบอร์ดแคสต์ข้อความไปยังห้องที่กำหนดไว้
@bot.tree.command(name='broadcast', description='บอร์ดแคสต์ข้อความไปยังห้องที่ตั้งค่าไว้')
async def broadcast(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    guild_id = interaction.guild_id
    if guild_id in broadcast_channels:
        for channel_id in broadcast_channels[guild_id]:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(message)
        await interaction.followup.send("บอร์ดแคสต์ข้อความเรียบร้อยแล้ว!", ephemeral=True)
    else:
        await interaction.followup.send("ยังไม่มีห้องที่ตั้งค่าให้บอร์ดแคสต์", ephemeral=True)


# ลิสต์ของบอส
boss_list = {
    1: "ชั้นล่าง โฮทูร่า",
    2: "ถ้ำ 7 ทิกดัลที่บ้าคลั่ง",
    3: "ถ้ำ 8 กัทฟิลเลียนชั่วร้าย",
    4: "ถ้ำ 9 แพนเดอเรปลุกพลัง",
    5: "พื้นที่ใหม่ 2 ฮาคีร์",
    6: "พื้นที่ใหม่ 3 ดามิโรส",
    7: "พื้นที่ใหม่ 4 คาฟคา",
    8: "อัศวินแห่งความพินาศ"
}


# คำสั่ง slash สำหรับบอร์ดแคสต์ข้อความแบบมีแพทเทิร์น
@bot.tree.command(name='pattern_broadcast', description='บอร์ดแคสต์ข้อความตามแพทเทิร์น')
@app_commands.describe(week="สัปดาห์ที่ต้องการบอร์ดแคสต์")
@app_commands.describe(boss_id="รหัสบอส (1-8)")
@app_commands.describe(date="วันที่ (เช่น 25/10/24)")
@app_commands.describe(time="เวลาที่จะบอร์ดแคสต์ (เช่น 18:00)")

async def pattern_broadcast(interaction: discord.Interaction, week: int, boss_id: int, date: str, time: str):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    if boss_id in boss_list:
        boss_name = boss_list[boss_id]
        message = f"Week {week}: {boss_name} {date} {time}"

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


# คำสั่ง slash สำหรับทักทาย
@bot.tree.command(name='hellbot', description='Replies with hello')
async def hellobot(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    await interaction.followup.send('Hello! It’s me, Bot DISCORD')

server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))