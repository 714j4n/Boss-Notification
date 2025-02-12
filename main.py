import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import datetime, asyncio, pytz

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
broadcast_channels = {}  # ✅
boss_channels = {}  # เก็บค่า channel_id ของแต่ละเซิร์ฟเวอร์ ✅
role_notifications = {}  # เก็บข้อมูล role ที่ใช้แท็กตอนแจ้งเตือนบอส ✅

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
# ----------------------------- setroom start -----------------------------
class SetRoomAction(Enum):
    ADD = "add"
    REMOVE = "remove"
    SET = "set"

class SetRoomOption(Enum):
    BROADCAST = "broadcast"
    NOTIFICATIONS = "notifications"
    BOSS = "boss"
    UPDATELOG = "updatelog"

@bot.tree.command(name='setroom', description='ตั้งค่าห้องต่างๆ เช่น บอร์ดแคสต์, แจ้งเตือนบอส และอัปเดตล็อก')
async def setroom(
        interaction: discord.Interaction,
        action: SetRoomAction,  # add, remove, set
        option: SetRoomOption,  # broadcast, notifications, boss, updatelog
        channel: discord.TextChannel
):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id

    if action == SetRoomAction.ADD:
        if option == SetRoomOption.BROADCAST:  # เพิ่มห้องบอร์ดแคสต์
            if guild_id not in broadcast_channels:
                broadcast_channels[guild_id] = []
            if channel.id not in broadcast_channels[guild_id]:
                broadcast_channels[guild_id].append(channel.id)
                await interaction.followup.send(f"✅ เพิ่มห้อง {channel.mention} เข้าสู่รายการบอร์ดแคสต์แล้ว!", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠ ห้อง {channel.mention} มีอยู่ในรายการบอร์ดแคสต์อยู่แล้ว", ephemeral=True)

    elif action == SetRoomAction.REMOVE:
        if option == SetRoomOption.NOTIFICATIONS:  # ลบห้องออกจากบอร์ดแคสต์
            if guild_id in broadcast_channels and channel.id in broadcast_channels[guild_id]:
                broadcast_channels[guild_id].remove(channel.id)
                await interaction.followup.send(f"✅ ลบห้อง {channel.mention} ออกจากรายการบอร์ดแคสต์แล้ว", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠ ไม่พบห้อง {channel.mention} ในรายการบอร์ดแคสต์", ephemeral=True)

    elif action == SetRoomAction.SET:
        if option == SetRoomOption.BOSS:  # ตั้งค่าช่องแจ้งเตือนบอส
            boss_channels[guild_id] = channel.id
            await interaction.followup.send(f"✅ ตั้งค่าช่อง {channel.mention} เป็นช่องแจ้งเตือนบอสเรียบร้อยแล้ว!", ephemeral=True)

        elif option == SetRoomOption.UPDATELOG:  # ตั้งค่าห้องอัปเดตล็อก
            update_log_channels[guild_id] = channel.id
            await interaction.followup.send(f"✅ ตั้งค่าห้อง update log เป็น {channel.mention} เรียบร้อย", ephemeral=True)

    else:
        await interaction.followup.send("⚠ คำสั่งไม่ถูกต้อง! โปรดเลือก action และ option ให้ถูกต้อง", ephemeral=True)
# ----------------------------- setroom end -----------------------------
# ----------------------------- setrole start -----------------------------
class SetRoleAction(Enum):
    ADD = "add"
    REMOVE = "remove"

class SetRoleOption(Enum):
    GUILD = "guild"
    ADMIN = "admin"
    BOSS = "boss"

@bot.tree.command(name='setrole', description='ตั้งค่า Role สำหรับเซิร์ฟเวอร์')
async def setrole(
        interaction: discord.Interaction,
        action: SetRoleAction,  # add, remove
        option: SetRoleOption,  # guild, admin, boss
        role: discord.Role = None,  # ใช้กับ add
        guild_name: str = None  # ใช้กับ guild option
):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id

    if action == SetRoleAction.ADD:
        if option == SetRoleOption.GUILD:
            if not guild_name or not role:
                return await interaction.followup.send("⚠ โปรดระบุกิลด์และ Role ที่ต้องการตั้งค่า!", ephemeral=True)
            if guild_id not in guild_active_roles:
                guild_active_roles[guild_id] = {}
            guild_active_roles[guild_id][guild_name] = role.id
            await interaction.followup.send(f"✅ ตั้งค่า Role **{role.name}** สำหรับกิลด์ **{guild_name}** แล้ว!", ephemeral=True)

        elif option == SetRoleOption.ADMIN:
            if not role:
                return await interaction.followup.send("⚠ โปรดระบุ Role ที่ต้องการตั้งเป็นแอดมิน!", ephemeral=True)
            admin_roles[guild_id] = role.name
            await interaction.followup.send(f"✅ ตั้งค่า Role แอดมินเป็น **{role.name}** แล้ว!", ephemeral=True)

        elif option == SetRoleOption.BOSS:
            if not role:
                return await interaction.followup.send("⚠ โปรดระบุ Role ที่ต้องการตั้งสำหรับแจ้งเตือนบอส!", ephemeral=True)
            boss_roles[guild_id] = role.id
            await interaction.followup.send(f"✅ ตั้งค่า Role สำหรับแจ้งเตือนบอสเป็น **{role.name}** แล้ว!", ephemeral=True)

    elif action == SetRoleAction.REMOVE:
        if option == SetRoleOption.GUILD:
            if not guild_name or guild_id not in guild_active_roles or guild_name not in guild_active_roles[guild_id]:
                return await interaction.followup.send("❌ ไม่พบกิลด์ที่ต้องการลบ!", ephemeral=True)
            del guild_active_roles[guild_id][guild_name]
            await interaction.followup.send(f"✅ ลบ Role ที่ผูกกับกิลด์ **{guild_name}** เรียบร้อย!", ephemeral=True)

        elif option == SetRoleOption.ADMIN:
            if guild_id in admin_roles:
                del admin_roles[guild_id]
                await interaction.followup.send(f"✅ ลบ Role แอดมินออกจากระบบแล้ว!", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ ยังไม่มี Role แอดมินที่ถูกตั้งค่า!", ephemeral=True)

        elif option == SetRoleOption.BOSS:
            if guild_id in boss_roles:
                del boss_roles[guild_id]
                await interaction.followup.send(f"✅ ลบ Role สำหรับแจ้งเตือนบอสออกจากระบบแล้ว!", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ ยังไม่มี Role บอสที่ถูกตั้งค่า!", ephemeral=True)

    else:
        await interaction.followup.send("⚠ คำสั่งไม่ถูกต้อง! กรุณาใช้: add หรือ remove", ephemeral=True)
# ----------------------------- setrole end -----------------------------
# ----------------------------- [boss] broadcast/notification start -----------------------------
class BossAction(Enum):
    BROADCAST = "broadcast"
    NOTIFICATION = "notification"
    LIST = "list"
    REMOVE_NOTIFICATION = "remove_notification"

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

class OwnerType(Enum):
    KNIGHT = "knight"
    BISHOP = "bishop"

local_tz = pytz.timezone("Asia/Bangkok")

@bot.tree.command(name='boss', description='จัดการคำสั่งเกี่ยวกับบอส')
@app_commands.describe(
    action="เลือกประเภทการทำงาน",
    boss_name="เลือกบอสจากรายการ (ใช้เมื่อจำเป็น)",
    date="วันที่ (เช่น 25/10/24, ใช้กับ broadcast)",
    time="เวลาบอสเกิด (เช่น 18:00, ใช้กับ broadcast)",
    hours="ตั้งค่าการแจ้งเตือนล่วงหน้ากี่ชั่วโมง (ใช้กับ notification)",
    minutes="ตั้งค่าการแจ้งเตือนล่วงหน้ากี่นาที (ใช้กับ notification)",
    role="เลือก Role ที่ต้องการแจ้งเตือน (ใช้กับ notification)",
    owner="เลือกเจ้าของการแจ้งเตือน (ใช้กับ notification)"
)
async def boss(
        interaction: discord.Interaction,
        action: BossAction,
        boss_name: BossName = None,
        date: str = None,
        time: str = None,
        hours: int = 0,
        minutes: int = 0,
        role: discord.Role = None,
        owner: OwnerType = None
):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id

    if action == BossAction.BROADCAST:
        if not boss_name or not date or not time:
            return await interaction.followup.send("❌ ต้องระบุบอส, วันที่ และเวลา!", ephemeral=True)
        message = f"### ✦～ 𝐁𝐨𝐬𝐬﹕{boss_name.value} 𝐃𝐚𝐭𝐞﹕{date} {time} ～✦"
        if guild_id in broadcast_channels:
            for channel_id in broadcast_channels[guild_id]:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(message)
            await interaction.followup.send("✅ บอร์ดแคสต์สำเร็จ!", ephemeral=True)
        else:
            await interaction.followup.send("❌ ยังไม่มีห้องที่ตั้งค่าให้บอร์ดแคสต์", ephemeral=True)

    elif action == BossAction.NOTIFICATION:
        if not boss_name or not owner:
            return await interaction.followup.send("❌ ต้องระบุชื่อบอสและเจ้าของการแจ้งเตือน!", ephemeral=True)
        now = datetime.datetime.now(local_tz)
        spawn_time = now + datetime.timedelta(hours=hours, minutes=minutes)
        if guild_id not in boss_notifications:
            boss_notifications[guild_id] = []
        boss_notifications[guild_id].append(
            {"boss_name": boss_name.name, "spawn_time": spawn_time, "owner": owner.value, "role": role.id})
        await interaction.followup.send(f"✅ ตั้งค่าแจ้งเตือนบอส {boss_name.value} เรียบร้อย!", ephemeral=True)
        await schedule_boss_notifications(guild_id, boss_name.name, spawn_time, owner.value, role)


    elif action == BossAction.LIST:

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

    elif action == BossAction.REMOVE_NOTIFICATION:
        if guild_id in boss_notifications and boss_name:
            boss_notifications[guild_id] = [notif for notif in boss_notifications[guild_id] if
                                            notif["boss_name"] != boss_name.name]
            await interaction.followup.send(f"✅ ลบการแจ้งเตือนของ {boss_name.value} เรียบร้อย!", ephemeral=True)
        else:
            await interaction.followup.send("❌ ไม่พบบอสที่ต้องการลบ!", ephemeral=True)

async def schedule_boss_notifications(guild_id, boss_name, spawn_time, owner, role):
    now = datetime.datetime.now(local_tz)
    time_until_spawn = (spawn_time - now).total_seconds()
    time_before_five_min = max(time_until_spawn - 300, 0)
    owner_icon = "💙" if owner == "knight" else "💚"

    if time_before_five_min > 0:
        await asyncio.sleep(time_before_five_min)
    if guild_id in boss_channels:
        channel = bot.get_channel(boss_channels[guild_id])
        if channel:
            embed = discord.Embed(title="𝐁𝐨𝐬𝐬 𝐍𝐨𝐭𝐢𝐟𝐢𝐜𝐚𝐭𝐢𝐨𝐧!!",
                                  description=f"{owner_icon} 𝐁𝐨𝐬𝐬 {boss_name} 𝐢𝐬 𝐬𝐩𝐚𝐰𝐧𝐢𝐧𝐠 𝐢𝐧 𝟓 𝐦𝐢𝐧𝐮𝐭𝐞𝐬! <@&{role.id}>",
                                  color=discord.Color.yellow())
            await channel.send(embed=embed)

    await asyncio.sleep(300)
    if guild_id in boss_channels:
        channel = bot.get_channel(boss_channels[guild_id])
        if channel:
            embed = discord.Embed(title="𝐁𝐨𝐬𝐬 𝐡𝐚𝐬 𝐬𝐩𝐚𝐰𝐧!!",
                                  description=f"{owner_icon} 𝐁𝐨𝐬𝐬 {boss_name} 𝐡𝐚𝐬 𝐒𝐩𝐚𝐰𝐧! <@&{role.id}>",
                                  color=discord.Color.red())
            await channel.send(embed=embed)
# ----------------------------- [boss] broadcast/notification end -----------------------------
# -------------------- สำหรับอัพเดทข้อมูล ชื่อ/อาชีพ/กิลด์ start--------------------
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
# -------------------- สำหรับอัพเดทข้อมูล ชื่อ/อาชีพ/กิลด์ end--------------------

server_on()

# เริ่มรันบอท
bot.run(os.getenv('TOKEN'))
