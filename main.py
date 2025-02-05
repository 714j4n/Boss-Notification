import discord
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ บอทออนไลน์ใน {len(bot.guilds)} เซิร์ฟเวอร์!")
    try:
        await bot.tree.sync()
        print("✅ ซิงค์ Slash Commands สำเร็จ!")
    except Exception as e:
        print(f"❌ ซิงค์คำสั่งล้มเหลว: {e}")

@bot.tree.command(name="test", description="ทดสอบ Slash Command")
async def test_command(interaction: discord.Interaction):
    await interaction.response.send_message("✅ คำสั่ง Slash ใช้งานได้!")

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
