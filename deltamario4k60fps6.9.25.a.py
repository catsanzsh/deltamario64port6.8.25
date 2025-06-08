from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import math

# I'm leaving the profiler here for you, sweetie. Sometimes it's fun to see just how fast you can make things go.
# import cProfile

# CAT-SAN'S FIX: Added the missing distance_xz helper function. Crucial for 2D plane calculations.
def distance_xz(a, b):
    """Calculates the distance between two entities on the XZ plane."""
    return distance(a.world_position.xz, b.world_position.xz)

app = Ursina()
window.title = 'Mario Platformer'
window.size = (800, 600)  # A bigger canvas for our masterpiece
window.vsync = True
window.fps_counter.enabled = True
window.exit_button.visible = False # Let's handle our own exits.

# --- Game State ---
# Keeps track of all the important little details.
class GameState:
    def __init__(self):
        self.stars = 0
        self.current_world = 'hub'
        self.unlocked_worlds = ['hub', 'grass']
        self.world_star_requirements = {
            'desert': 3,
            'ice': 8,
            'lava': 15
        }

game_state = GameState()

# --- Player Controller ---
# This is you, darling. Powerful, fast, and ready for anything.
class MarioController(Entity):
    # Constants for fine-tuning your moves
    SPEED = 7
    RUN_ACCEL = 10
    RUN_DECEL = 8
    JUMP_FORCE = 10
    GRAVITY = 30
    AIR_CONTROL = 0.8
    TRIPLE_JUMP_MULTS = (1.0, 1.2, 1.5) # Normal, Double, Triple
    LONG_JUMP_MIN_SPEED = 4
    LONG_JUMP_FORWARD_BOOST = 10
    LONG_JUMP_VERTICAL_BOOST = 7
    WALL_JUMP_FORCE = 9
    WALL_JUMP_KICKOFF = 6

    def __init__(self, **kwargs):
        super().__init__(
            model='cube',
            color=color.red,
            scale=(0.8, 1.8, 0.8), # A bit taller, more heroic
            position=(0, 5, 0),
            **kwargs
        )
        # Player properties
        self.velocity = Vec3(0)
        self.grounded = False
        self.jump_count = 0
        self.jump_timer = 0.0
        self.max_jump_chain_time = 0.4 # A tighter window for more skilled moves
        self.can_wall_jump = False
        self.wall_normal = None
        
        # CAT-SAN'S FIX: Stored the original scale to prevent animation bugs.
        self.original_scale = self.scale

        # Camera setup
        self.camera_pivot = Entity(parent=self, y=1)
        camera.parent = self.camera_pivot
        camera.position = (0, 1, -10)
        camera.rotation_x = 10
        mouse.locked = True

    def update(self):
        self.handle_input()
        self.update_physics()
        self.update_camera()

        # Fall out of the world
        if self.y < -30:
            self.respawn()

    def handle_input(self):
        # Movement input
        move_direction = Vec3(
            held_keys['d'] - held_keys['a'],
            0,
            held_keys['w'] - held_keys['s']
        ).normalized()

        # Align movement to camera
        camera_forward = Vec3(camera.forward.x, 0, camera.forward.z).normalized()
        world_move = camera_forward * move_direction.z + camera.right * move_direction.x
        
        # Apply air control or ground movement
        if not self.grounded:
            self.velocity.x = lerp(self.velocity.x, world_move.x * self.SPEED, time.dt * self.AIR_CONTROL)
            self.velocity.z = lerp(self.velocity.z, world_move.z * self.SPEED, time.dt * self.AIR_CONTROL)
        else:
            # CAT-SAN'S FIX: Implemented smooth acceleration/deceleration using the constants you already had. Feels much better.
            target_velocity_xz = world_move.xz * self.SPEED
            if target_velocity_xz.length() > 0:
                 self.velocity.xz = lerp(self.velocity.xz, target_velocity_xz, time.dt * self.RUN_ACCEL)
            else:
                 self.velocity.xz = lerp(self.velocity.xz, Vec2(0,0), time.dt * self.RUN_DECEL)

            # Reset jump chain if the window expires
            if self.jump_timer > self.max_jump_chain_time:
                self.jump_count = 0
        
        self.jump_timer += time.dt


    def jump(self):
        # Wall Jump
        if self.can_wall_jump:
            self.velocity.y = self.WALL_JUMP_FORCE
            # Kick away from the wall
            self.velocity += self.wall_normal * self.WALL_JUMP_KICKOFF
            self.jump_count = 1 # A wall jump counts as the first jump
            self.can_wall_jump = False
            return

        # Ground Jumps
        if self.grounded:
            self.grounded = False
            running_speed = Vec2(self.velocity.x, self.velocity.z).length()

            # Long Jump
            if running_speed > self.LONG_JUMP_MIN_SPEED and held_keys['shift']:
                self.velocity.y = self.LONG_JUMP_VERTICAL_BOOST
                self.velocity += self.velocity.normalized() * self.LONG_JUMP_FORWARD_BOOST
                self.jump_count = 0 # Long jump resets the chain
            # Triple Jump Chain
            else:
                self.jump_count = min(self.jump_count + 1, 3)
                self.velocity.y = self.JUMP_FORCE * self.TRIPLE_JUMP_MULTS[self.jump_count - 1]
                if self.jump_count == 3:
                    # CAT-SAN'S FIX: Used the stored original_scale to ensure the player returns to the correct size.
                    self.animate_scale(self.original_scale * 1.2, duration=0.1, curve=curve.out_quad)
                    self.animate_scale(self.original_scale, duration=0.2, delay=0.1, curve=curve.in_quad)

            self.jump_timer = 0

    def update_physics(self):
        # Apply gravity
        if not self.grounded:
            self.velocity.y -= self.GRAVITY * time.dt
        
        # Move and collide
        movement = self.velocity * time.dt
        
        # Use a box cast for robust collision detection
        # The logic here was solid, no changes needed. A little complex, but it gets the job done.
        hit_info = boxcast(self.position + Vec3(0,self.scale_y/2,0), direction=movement.normalized(), 
                           distance=movement.length() + 0.2, thickness=(self.scale_x, self.scale_y), ignore=[self,])

        if hit_info.hit:
            # Move player to the point of impact
            self.position += movement.normalized() * hit_info.distance
            # Slide along walls by removing velocity component into the wall
            self.velocity = self.velocity - hit_info.world_normal * Vec3.dot(self.velocity, hit_info.world_normal)
        else:
            self.position += movement

        # Ground and Wall detection
        self.grounded = False
        self.can_wall_jump = False
        
        # Downward check for ground
        ground_check = boxcast(self.world_position + Vec3(0,0.1,0), direction=Vec3(0,-1,0), distance=0.2, thickness=(0.9,0.1), ignore=[self,])
        if ground_check.hit:
            # Check if we're landing on top of something, not the side
            if ground_check.world_normal.y > 0.7 and self.velocity.y <= 0:
                self.y = ground_check.world_point.y
                self.velocity.y = 0
                self.grounded = True
                self.jump_count = 0

        # Wall check if we are in the air
        if not self.grounded:
            side_check = boxcast(self.position + Vec3(0,self.scale_y/2,0), direction=self.velocity.xz.normalized(),
                                 distance=0.51, thickness=(self.scale_x, self.scale_y*0.8), ignore=[self,])
            if side_check.hit and side_check.world_normal.y < 0.7:
                self.can_wall_jump = True
                self.wall_normal = side_check.world_normal
                # Slide down walls slowly
                if self.velocity.y < 0:
                    self.velocity.y = max(self.velocity.y, -3)


    def update_camera(self):
        self.camera_pivot.rotation_y += mouse.velocity[0] * 40
        self.camera_pivot.rotation_x -= mouse.velocity[1] * 40
        self.camera_pivot.rotation_x = clamp(self.camera_pivot.rotation_x, -80, 80)

    def respawn(self):
        if game_state.current_world == 'hub':
            self.position = (0, 2, 0)
        else:
            # Find a safe spawn point
            self.position = find_safe_spawn_point()
        self.velocity = Vec3(0)

    def input(self, key):
        if key == 'space':
            self.jump()
        if key == 'escape':
            mouse.locked = not mouse.locked
        if key == 'r':
            load_world('hub')

# --- Game Objects ---

class Star(Entity):
    def __init__(self, position=(0, 1, 0), **kwargs):
        super().__init__(
            parent=scene, # Stars should be independent of the level mesh for simplicity
            model='sphere', # A nice round star
            texture='white_cube',
            color=color.yellow,
            scale=0.6,
            position=position,
            collider='sphere',
            **kwargs
        )
        self.rotation_speed = 50
        self.float_amplitude = 0.2
        self.float_speed = 2
        self.start_y = position[1]

    def update(self):
        self.rotation_y += self.rotation_speed * time.dt
        self.y = self.start_y + math.sin(time.time() * self.float_speed) * self.float_amplitude
        if self.enabled and distance_xz(self, player) < 1.2 and abs(self.y - player.y) < 2:
            self.collect()

    def collect(self):
        game_state.stars += 1
        ui.star_text.text = f'★ {game_state.stars}' # Immediate feedback
        ui.star_text.animate_scale(1.5, duration=0.1)
        ui.star_text.animate_scale(1, duration=0.2, delay=0.1)
        
        # A more satisfying collection effect
        # CAT-SAN'S FIX: Swapped 'powerup' for 'coin', a sound that actually comes with Ursina.
        Audio('coin', pitch=random.uniform(0.9, 1.1), volume=0.5)
        for i in range(5):
            e = Entity(parent=camera.ui, model='quad', color=color.gold, scale=random.uniform(0.01, 0.05),
                       position=self.world_position, rotation_z=random.uniform(0,360))
            e.animate_position((ui.star_text.x, ui.star_text.y), duration=0.5, curve=curve.in_quad)
            e.animate_scale(0, duration=0.5)
            destroy(e, delay=0.5)
        
        self.disable() # Disabling is faster than destroying and prevents double collection
        invoke(destroy, self, delay=1)


class Goomba(Entity):
    def __init__(self, position=(0, 0, 0), patrol_area=5, **kwargs):
        super().__init__(
            parent=scene, # Also independent of the level mesh
            model='cube',
            color=color.rgb(139, 69, 19), # A proper brown
            scale=(1, 0.8, 1),
            position=position,
            collider='box',
            **kwargs
        )
        self.move_speed = 2
        self.direction = random.choice([Vec3(1,0,0), Vec3(-1,0,0), Vec3(0,0,1), Vec3(0,0,-1)])
        self.start_position = Vec3(position)
        self.patrol_area = patrol_area

    def update(self):
        # Ledge and wall detection
        wall_check = raycast(self.world_position, self.direction, distance=0.6, ignore=[self, player])
        ledge_check = not raycast(self.world_position + self.direction*0.6, Vec3(0,-1,0), distance=2, ignore=[self, player]).hit

        if wall_check.hit or ledge_check or distance_xz(self.position, self.start_position) > self.patrol_area:
            self.direction = random.choice([Vec3(1,0,0), Vec3(-1,0,0), Vec3(0,0,1), Vec3(0,0,-1)])

        self.position += self.direction * self.move_speed * time.dt
        
        # Interaction with player
        if self.intersects(player).hit:
            # Player stomps Goomba
            if player.velocity.y < -1 and player.y > self.y + 0.5:
                self.defeat()
                player.velocity.y = 8 # Bounce
            # Goomba hurts player
            else:
                player.respawn()

    def defeat(self):
        # CAT-SAN'S FIX: Replaced 'hit' with a low-pitched 'blip' for a satisfying squish sound.
        Audio('blip', pitch=0.5, volume=0.7)
        self.disable()
        self.animate_scale_y(0.1, duration=0.2)
        self.animate_color(color.clear, duration=0.2)
        destroy(self, delay=0.3)

class WorldPortal(Entity):
    def __init__(self, position, world_name, required_stars=0, color_theme=color.blue):
        super().__init__(
            parent=scene, # Portals are part of the main scene, not the level
            model='cube',
            texture='white_cube',
            color=color_theme,
            scale=(2, 3, 0.5),
            position=position,
            collider='box',
        )
        self.world_name = world_name
        self.required_stars = required_stars
        self.original_color = color_theme
        self.unlocked = False

        # Fancy text above the portal
        self.label = Text(parent=self, text=f"{world_name.title()}\n★ {required_stars}",
                          scale=5, position=(0, 0.6, -0.51), origin=(0,0), color=color.black)

    def update(self):
        self.rotation_y += time.dt * 15
        self.unlocked = game_state.stars >= self.required_stars

        if self.unlocked:
            self.color = lerp(self.color, self.original_color, time.dt*2)
            self.label.color = color.white
        else:
            self.color = lerp(self.color, color.gray, time.dt*2)
            self.label.color = color.dark_gray
        
        # Check for intersection and clear instruction text if player moves away
        if self.intersects(player).hit:
            if self.unlocked:
                ui.show_instruction(f"Press 'E' to enter {self.world_name.title()}")
                if held_keys['e']:
                    self.enter_world()
            else:
                ui.show_instruction(f"Need {self.required_stars - game_state.stars} more stars!")
        elif ui.instruction_text.text.startswith(f"Press 'E' to enter {self.world_name.title()}"):
            ui.hide_instruction()

    def enter_world(self):
        Audio('blip', volume=0.5)
        game_state.current_world = self.world_name
        load_world(self.world_name)

# --- UI ---
class UI(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui)
        self.star_text = Text(parent=self, text=f'★ {game_state.stars}', 
                              position=window.top_left + Vec2(0.05, -0.05),
                              scale=2, color=color.yellow, origin=(-0.5, 0.5))
        
        self.instruction_text = Text(parent=self, text='', position=(0, -0.4), scale=1.5,
                                     origin=(0,0), background=True)
        self.instruction_text.enabled = False
        self.instruction_hider = None

    def show_instruction(self, text, duration=2):
        if self.instruction_hider:
            self.instruction_hider.kill()
        self.instruction_text.text = text
        self.instruction_text.enabled = True
        self.instruction_hider = invoke(self.hide_instruction, delay=duration)

    def hide_instruction(self):
        self.instruction_text.enabled = False

# --- World Generation ---
level_parent = Entity()
active_level_objects = []

def create_level_from_data(platforms, color_theme):
    global level_parent
    # We combine all static geometry into one for huge performance gains. Your idea, and a brilliant one.
    verts = []
    uvs = []
    tris = []
    i = 0
    for p in platforms: # p is a tuple of (pos_x, pos_y, pos_z, scale_x, scale_y, scale_z)
        pos = Vec3(p[0], p[1], p[2])
        scale = Vec3(p[3], p[4], p[5])
        # Manually add vertices for a cube, transformed by position and scale
        for v in Cube.model.vertices:
            verts.append(pos + (v-.5) * scale)
        uvs.extend(Cube.model.uvs)
        tris.extend([t+i for t in (0,1,2,0,2,3, 4,5,6,4,6,7, 8,9,10,8,10,11, 12,13,14,12,14,15, 16,17,18,16,18,19, 20,21,22,20,22,23)])
        i += 24

    if verts:
        level_parent = Entity(model=Mesh(vertices=verts, triangles=tris, uvs=uvs, static=True), 
                              texture='white_cube', texture_scale=(1,1),
                              color=color_theme, collider='mesh')
    else: # Handle cases with no platforms
        level_parent = Entity()

def clear_world():
    global level_parent, active_level_objects
    # Destroying one parent is much cleaner and faster.
    destroy(level_parent)
    for obj in active_level_objects:
        destroy(obj)
    active_level_objects.clear()
    # Hide portals not in the hub
    for p in scene.entities:
        if isinstance(p, WorldPortal):
            p.enabled = False

world_registry = {}
def world(func):
    """A decorator to register world creation functions."""
    world_registry[func.__name__] = func
    return func

@world
def hub():
    clear_world()
    platforms = [
        (0, -1, 0, 30, 1, 30), # Ground
    ]
    create_level_from_data(platforms, color.lime_green)

    # Scenery (no colliders needed, just for looks)
    castle = Entity(parent=level_parent, model='cube', color=color.light_gray, scale=(8,10,6), position=(0,4,-15))
    active_level_objects.append(castle)
    for i in range(12):
        tree = Entity(parent=level_parent, model='cube', color=color.dark_green, 
               scale=(1, random.randint(3,6), 1), 
               position=(random.uniform(-14, 14), .5, random.uniform(-14, 14)))
        active_level_objects.append(tree)
    
    # Enable and position portals for the hub
    for p in scene.entities:
        if isinstance(p, WorldPortal):
            p.enabled = True

    ui.show_instruction("Welcome! WASD to move, Mouse to look, Space to jump.", 5)

@world
def grass():
    clear_world()
    platforms = [
        (0, 0, 0, 20, 1, 20), (8, 2, 5, 8, 1, 8), (-10, 4, -8, 6, 1, 6),
        (5, 6, 12, 10, 1, 4), (0, 8, -5, 3, 1, 3)
    ]
    create_level_from_data(platforms, color.green)
    active_level_objects.extend([
        Star(position=(0, 2, 0)), Star(position=(8, 5, 5)), Star(position=(-10, 7, -8)), Star(position=(5, 9, 12)), Star(position=(0, 12, -5)),
        Goomba(position=(3, 1, 3)), Goomba(position=(-5, 1, -2)), Goomba(position=(8, 4, 8)), Goomba(position=(-8, 6, -8))
    ])

@world
def desert():
    clear_world()
    platforms = [
        (0, 0, 0, 25, 1, 25), (15, 3, 8, 6, 1, 6), (-12, 5, -6, 8, 1, 4), 
        (8, 8, -15, 4, 1, 8), (0, 4, 10, 3, 8, 3) # Pyramid
    ]
    create_level_from_data(platforms, color.sand)
    active_level_objects.extend([
        Star(position=(0, 2, 0)), Star(position=(15, 6, 8)), Star(position=(-12, 8, -6)), Star(position=(8, 11, -15)), Star(position=(0, 10, 10)),
        Goomba(position=(4, 1, -4)), Goomba(position=(-6, 1, 5)), Goomba(position=(15, 5, 10))
    ])

@world
def ice():
    clear_world()
    player.SPEED = 8 # Slippery!
    platforms = [
        (0, -1, 0, 20, 1, 20), (15, 4, 10, 6, 1, 6), (-12, 7, -8, 8, 1, 5), (10, 10, -12, 5, 1, 8)
    ]
    create_level_from_data(platforms, color.light_gray)
    active_level_objects.extend([
        Star(position=(0, 2, 0)), Star(position=(15, 7, 10)), Star(position=(-12, 10, -8)), Star(position=(10, 13, -12)), Star(position=(-5, 5, 5)),
        Goomba(position=(5, 1, -3)), Goomba(position=(-4, 1, 6)), Goomba(position=(15, 6, 12))
    ])

@world
def lava():
    clear_world()
    platforms = [
        (0, 0, 0, 8, 1, 8), (12, 5, 8, 5, 1, 5), (-10, 8, -10, 6, 1, 4), (8, 12, -15, 4, 1, 6)
    ]
    create_level_from_data(platforms, color.dark_gray)
    # Lava floor that hurts you
    lava_pool = Entity(model='quad', color=color.orange.tint(-0.2), 
                       scale=40, position=(0, -2, 0), rotation_x=90)
    def lava_check():
        if player.y < lava_pool.y + 1:
            player.respawn()
    lava_pool.update = lava_check
    active_level_objects.append(lava_pool)
    active_level_objects.extend([
        Star(position=(0, 3, 0)), Star(position=(12, 8, 8)), Star(position=(-10, 11, -10)), Star(position=(8, 15, -15)), Star(position=(5, 3, -5)),
        Goomba(position=(6, 1, -2)), Goomba(position=(-3, 1, 4)), Goomba(position=(12, 7, 10))
    ])


def load_world(world_name):
    player.SPEED = MarioController.SPEED # Reset speed on world change
    if world_name in world_registry:
        world_registry[world_name]()
    player.respawn()
    ui.hide_instruction()

def find_safe_spawn_point():
    # Find the highest platform to spawn on
    if level_parent and level_parent.model and level_parent.model.vertices:
        platforms = [v for v in level_parent.model.vertices]
        if platforms:
            highest_y = -9999
            for v in platforms:
                if v.y > highest_y:
                    highest_y = v.y
            return Vec3(0, highest_y + 2, 0)
    return Vec3(0, 5, -10) # Fallback

# --- Initial Setup ---
# Create portals once, they will be enabled/disabled by the world loader
WorldPortal((-10, 1, 8), 'grass', 0, color.green)
WorldPortal((10, 1, 8), 'desert', 3, color.orange)
WorldPortal((-10, 1, -8), 'ice', 8, color.cyan)
WorldPortal((10, 1, -8), 'lava', 15, color.red)
player = MarioController()
ui = UI()
sun = DirectionalLight()
sun.look_at(Vec3(1, -1.5, -1))
sky = Sky() # Default sky is fine

# Load the hub world to start
load_world('hub')

# Start the engine, darling.
app.run()
