import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta

from myserver import server_on

# กำหนด prefix ของคำสั่ง
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

# บันทึกข้อมูลบอสถาวร
boss_timers = []
broadcast_channels = {}
boss_alert_channels = {}  # บันทึกห้องแจ้งเตือนบอสของแต่ละเซิร์ฟเวอร์

# ลิสต์ของบอส
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

# คำสั่งตอบสนองเมื่อบอทออนไลน์
@bot.event
async def on_ready():
    print("Bot Online!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# คำสั่ง slash สำหรับทักทาย
@bot.tree.command(name='hellbot', description='Replies with hello')
async def hellobot(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    await interaction.followup.send('Hello! It’s me, Bot DISCORD')

# -------- ระบบกำหนดห้องแจ้งเตือนบอส --------
@bot.tree.command(name="set_boss_channel", description="กำหนดห้องสำหรับแจ้งเตือนบอส")
async def set_boss_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild_id
    boss_alert_channels[guild_id] = channel.id
    await interaction.response.send_message(f"✅ ตั้งห้องแจ้งเตือนบอสเป็น {channel.mention} แล้ว!", ephemeral=True)

# -------- ระบบตั้งเวลาแจ้งเตือนบอส --------
class BossView(discord.ui.View):
    def __init__(self, boss_name, alert_time, role, owner):
        super().__init__(timeout=30)
        self.boss_name = boss_name
        self.alert_time = alert_time
        self.role = role
        self.owner = owner

    @discord.ui.button(label="✅ ยืนยัน", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        boss_timers.append((self.boss_name, self.alert_time, self.role, self.owner))
        await interaction.response.edit_message(content=f"✅ ตั้งเวลา {self.boss_name} {self.alert_time.strftime('%H:%M')} เรียบร้อย!", view=None)

@bot.tree.command(name="boss_set", description="ตั้งเวลาแจ้งเตือนบอส")
@app_commands.describe(boss="เลือกชื่อบอส", time="กำหนดเวลา (HH:MM)", role="เลือกยศที่ต้องการแท็ก", owner="ระบุเจ้าของบอส (knight/bishop)")
async def boss_set(interaction: discord.Interaction, boss: str, time: str, role: discord.Role, owner: str):
    if owner.lower() not in ["knight", "bishop"]:
        await interaction.response.send_message("❌ โปรดเลือกเจ้าของบอสเป็น knight หรือ bishop", ephemeral=True)
        return
    try:
        user_time = datetime.strptime(time, "%H:%M")
        view = BossView(boss, user_time, role, owner)
        await interaction.response.send_message(f"ต้องการตั้งเวลา {boss} ({owner}) ที่ {user_time.strftime('%H:%M')} ใช่หรือไม่?", view=view)
    except ValueError:
        await interaction.response.send_message("❌ โปรดใส่เวลาในรูปแบบ HH:MM", ephemeral=True)

@tasks.loop(seconds=30)
async def check_boss_timers():
    now = datetime.now()
    for boss, alert_time, role, owner in boss_timers[:]:
        time_diff = (alert_time - now).total_seconds()
        if 300 <= time_diff < 330:
            await send_boss_alert(boss, role, owner, "📢 อีก 5 นาที บอสกำลังจะเกิด!")
        elif 0 <= time_diff < 30:
            await send_boss_alert(boss, role, owner, "⚔️ บอสเกิดแล้ว!")
            boss_timers.remove((boss, alert_time, role, owner))

async def send_boss_alert(boss, role, owner, message):
    guild_id = role.guild.id
    channel_id = boss_alert_channels.get(guild_id)
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(title=f"บอส: {boss} ({owner})", description=f"🕒 เวลาเกิด: {datetime.now().strftime('%H:%M')}", color=discord.Color.red())
            embed.add_field(name="แจ้งเตือน", value=message, inline=False)
            await channel.send(content=role.mention, embed=embed)

# -------- คำสั่ง slash สำหรับเพิ่มห้องเพื่อบอร์ดแคสต์ --------
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

@bot.event
async def on_ready():
    print("✅ บอทออนไลน์!")
    check_boss_timers.start()

server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
