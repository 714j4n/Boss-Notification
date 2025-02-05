import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta

from myserver import server_on

# กำหนด prefix และ intents
intents = discord.Intents.default()
intents.message_content = True  # เปิดให้ bot อ่าน message ได้
bot = commands.Bot(command_prefix='!', intents=intents)

# บันทึกข้อมูลบอสถาวร
boss_timers = []
broadcast_channels = {}
boss_alert_channels = {}  # บันทึกห้องแจ้งเตือนบอสของแต่ละเซิร์ฟเวอร์

# รายชื่อบอส
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

# คำสั่ง sync command หากยังไม่พบ Slash Commands
@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ คำสั่งทั้งหมดซิงค์เรียบร้อยแล้ว!")

# คำสั่ง slash สำหรับทักทาย
@bot.tree.command(name='hellbot', description='Replies with hello')
async def hellobot(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # เพิ่มการ defer
    await interaction.followup.send('Hello! It’s me, Bot DISCORD')

@bot.event
async def on_ready():
    print("✅ บอทออนไลน์! กำลังซิงค์ Slash Commands...")
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} command(s) synced successfully!")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    check_boss_timers.start()

server_on()

# เริ่มรันบอท
TOKEN = os.getenv('TOKEN')
if not TOKEN:
    print("❌ Error: TOKEN ไม่พบใน environment variables!")
else:
    bot.run(TOKEN)
