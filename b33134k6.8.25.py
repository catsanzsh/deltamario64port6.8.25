from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

app = Ursina()
window.title = 'Peach\'s Castle'
window.size = (600,400)
window.exit_button.visible = False
window.fullscreen = False
window.fps_counter.enabled = False

# Skybox
sky = Entity(
    model='cube',
    texture='sky_default',
    scale=(100,100,100),
    shader=None
)

# Castle floor
floor = Entity(
    model='cube',
    texture='grass',
    scale=(100,0.1,100),
    collider='box'
)

# Main castle structure
castle = Entity(model='cube', color=color.brown, scale=(30,20,30), collider='box')
castle.position = (0,10,-30)

# Towers
for i in range(4):
    angle = i * 90
    tower = Entity(
        model='cylinder',
        color=color.brown,
        scale=(5,15,5),
        rotation_y=angle,
        x=sin(angle)*18,
        z=cos(angle)*18,
        y=20
    )

# Windows
for y in range(5):
    for x in range(2):
        window = Entity(
            model='cube',
            color=color.white,
            scale=(4,5,0.1),
            x=(-10 + x*20),
            z=25,
            y=(y*5 + 10)
        )

# Main door
door = Entity(
    model='cube',
    color=color.brown,
    scale=(8,12,0.5),
    z=30,
    y=10
)
door_frame = Entity(model='cube', color=color.black, scale=(10,14,0.1), z=29.5, y=10)

# Flag
flagpole = Entity(model='cube', color=color.gray, scale=(0.5,20,0.5), x=0, z=-20, y=10)
flag = Entity(model='cube', color=color.red, scale=(5,4,1), x=2.5, z=-15, y=23)
flag_white = Entity(model='cube', color=color.white, scale=(2.5,4,1), x=3.75, z=-15, y=23)

# Moat
moat = Entity(
    model='cube',
    color=color.blue,
    scale=(35,0.5,35),
    y=9.5,
    z=-30,
    collider='box'
)

# HUD Elements (SM64-style)
hud = Entity(parent=camera.ui)
lives = Text(text='x3', scale=2, origin=(-1.8,0), position=(-0.8,0.4), color=color.white)
coins = Text(text='0', scale=2, origin=(-1.8,0), position=(-0.5,0.4), color=color.white)
stars = Text(text='0', scale=2, origin=(-1.8,0), position=(-0.2,0.4), color=color.white)
timer = Text(text='00:00', scale=2, origin=(-1.8,0), position=(-0.8,-0.35), color=color.white)

# Camera controls
player = FirstPersonController()
player.speed = 5
player.cursor.visible = False
player.position = (0,15,-40)

def update():
    timer.text = str(int(time.time() - start_time)).zfill(2)+':00'

start_time = time.time()
app.run()
