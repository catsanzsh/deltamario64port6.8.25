from ursina import *
# FirstPersonController is not used, so it's removed from imports.
import random

app = Ursina()
window.title = 'Mario Platformer'
window.size = (800, 600)
window.fps_counter.enabled = True
window.exit_button.visible = False

def distance_xz(a, b):
    """Calculates the squared distance on the XZ plane for efficiency."""
    return (a.x - b.x)**2 + (a.z - b.z)**2

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

class MarioController(Entity):
    SPEED = 7
    JUMP_FORCE = 9
    GRAVITY = 25
    
    def __init__(self, **kwargs):
        super().__init__(
            model='cube',
            color=color.red,
            scale=(0.8, 1.8, 0.8),
            collider='box',
            **kwargs
        )
        self.velocity = Vec3(0)
        self.grounded = False
        
        # Camera and mouse setup for a third-person view
        self.camera_pivot = Entity(parent=self, y=1.5)
        camera.parent = self.camera_pivot
        camera.position = (0, 1, -10)
        camera.rotation_x = 10
        mouse.locked = True
        self.mouse_sensitivity = Vec2(80, 80)

    def update(self):
        self.handle_camera()
        self.handle_input()
        self.update_physics()

    def handle_camera(self):
        """Rotates the player and camera pivot based on mouse movement."""
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity.x * time.dt
        self.camera_pivot.rotation_x -= mouse.velocity[1] * self.mouse_sensitivity.y * time.dt
        self.camera_pivot.rotation_x = clamp(self.camera_pivot.rotation_x, -20, 40)

    def handle_input(self):
        """Handles keyboard input for movement and jumping."""
        move_direction = Vec3(
            held_keys['d'] - held_keys['a'],
            0,
            held_keys['w'] - held_keys['s']
        ).normalized()

        # Set horizontal velocity based on input and player rotation
        move = self.forward * move_direction.z + self.right * move_direction.x
        self.velocity.x = move.x * self.SPEED
        self.velocity.z = move.z * self.SPEED
        
        if self.grounded and held_keys['space']:
            self.jump()

    def jump(self):
        self.velocity.y = self.JUMP_FORCE
        self.grounded = False

    def update_physics(self):
        """Applies gravity and handles collisions."""
        # Apply gravity only when airborne
        if not self.grounded:
            self.velocity.y -= self.GRAVITY * time.dt

        # Use Ursina's built-in move method which handles collisions automatically
        self.move(self.velocity * time.dt)
        
        # A robust ground check using a downward raycast
        # This checks for ground slightly below the player's feet
        ground_ray = raycast(self.world_position + Vec3(0,0.1,0), direction=(0, -1, 0), ignore=[self,], distance=0.2)
        
        if ground_ray.hit:
            if self.velocity.y < 0: # Only zero velocity if falling onto the ground
                self.velocity.y = 0
            self.grounded = True
        else:
            self.grounded = False
            
        # Respawn if the player falls out of the world
        if self.y < -20:
            self.respawn()

    def respawn(self):
        spawn_point = {
            'hub': (0, 2, 0),
            'grass': (0, 1, 0),
            'desert': (0, 1, 0),
            'ice': (0, 1, 0),
            'lava': (0, 1, 0)
        }
        self.position = spawn_point.get(game_state.current_world, (0, 5, 0))
        self.velocity = Vec3(0)
        self.grounded = False

class Star(Entity):
    def __init__(self, position=(0, 1, 0), **kwargs):
        super().__init__(
            model='sphere',
            color=color.yellow,
            scale=0.6,
            position=position,
            collider='sphere',
            always_on_top=True,
            **kwargs
        )
        self.rotation_speed = 100
        self.start_y = self.y

    def update(self):
        self.rotation_y += self.rotation_speed * time.dt
        self.y = self.start_y + sin(time.time() * 2) * 0.1 # Bobbing effect
        if distance_xz(self.position, player.position) < 1.2**2: # Use squared distance
            self.collect()

    def collect(self):
        game_state.stars += 1
        ui.star_text.text = f'★ {game_state.stars}'
        Audio('coin_sound.wav', pitch=random.uniform(0.9, 1.1), volume=0.5) # Example sound
        self.disable()

class Goomba(Entity):
    def __init__(self, position=(0, 0, 0), **kwargs):
        super().__init__(
            model='cube',
            texture='brick',
            color=color.brown,
            scale=(1, 0.8, 1),
            position=position,
            collider='box',
            **kwargs
        )
        self.move_speed = 2
        self.direction = random.choice([Vec3(1,0,0), Vec3(-1,0,0), Vec3(0,0,1), Vec3(0,0,-1)])

    def update(self):
        # Move and check for wall collisions to turn around
        hit_info = self.move(self.direction * self.move_speed * time.dt)
        if hit_info.hit and hit_info.entity is not player:
            self.direction = -self.direction

        # Check for interaction with the player
        if self.enabled and self.intersects(player).hit:
            # Player stomps the goomba if falling from above
            if player.velocity.y < -1 and player.y > self.y + 0.5:
                self.defeat()
            # Otherwise, the player gets hurt
            else:
                player.respawn()

    def defeat(self):
        player.velocity.y = 5 # Give player a small bounce
        self.collider = None # Disable further collisions
        self.animate_scale_y(0.1, duration=0.2)
        invoke(self.disable, delay=0.2) # Disable after the animation finishes

class WorldPortal(Entity):
    def __init__(self, position, world_name, required_stars=0, **kwargs):
        super().__init__(
            model='cube',
            texture='white_cube',
            color=color.azure,
            scale=(2, 3, 0.5),
            position=position,
            collider='box',
            **kwargs
        )
        self.world_name = world_name
        self.required_stars = required_stars
        self.text_label = Text(parent=self, text=f'{world_name.title()}\n★ {required_stars}', y=1, scale=5, origin=(0,0))

    def update(self):
        # Make the portal visually pulse
        self.color = color.azure.tint(sin(time.time()*2) * 0.2)
        # Check if player can enter
        if self.intersects(player).hit and held_keys['e']:
            if game_state.stars >= self.required_stars:
                load_world(self.world_name)
            else:
                # Provide feedback if requirements aren't met
                self.text_label.text = f'Need ★ {self.required_stars}!'
                self.text_label.shake()
                invoke(lambda: setattr(self.text_label, 'text', f'{self.world_name.title()}\n★ {self.required_stars}'), delay=2)

class UI(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui)
        self.star_text = Text(
            text=f'★ {game_state.stars}',
            position=window.top_left + Vec2(0.05, -0.05),
            scale=2,
            color=color.yellow,
            origin=(-0.5, 0.5)
        )

# Global container for all dynamically loaded world objects
world_objects = []

def clear_world():
    global world_objects
    for obj in world_objects:
        destroy(obj)
    world_objects.clear()

def create_level(platforms, color_theme, sky_texture):
    """Creates platforms and sets the sky."""
    for p in platforms:
        platform = Entity(
            model='cube',
            color=color_theme,
            texture='white_cube',
            scale=p[:3],
            position=p[3:],
            collider='box'
        )
        world_objects.append(platform)
    # Add a skybox
    sky = Sky(texture=sky_texture)
    world_objects.append(sky)

def load_world(world_name):
    clear_world()
    game_state.current_world = world_name
    
    # World data dictionary
    world_data = {
        'hub': {
            'platforms': [(30, 1, 30, 0, 0, 0)],
            'color': color.gray,
            'sky': 'sky_sunset',
            'objects': [
                (WorldPortal, {'position': (-10, 1.5, 8), 'world_name': 'grass', 'required_stars': 0}),
                (WorldPortal, {'position': (10, 1.5, 8), 'world_name': 'desert', 'required_stars': 3})
            ]
        },
        'grass': {
            'platforms': [
                (20, 1, 20, 0, 0, 0), (8, 1, 8, 8, 2, 5),
                (6, 1, 6, -10, 4, -8), (10, 1, 4, 5, 6, 12),
                (3, 1, 3, 0, 8, -5)
            ],
            'color': color.green,
            'sky': 'sky_default',
            'objects': [
                (Star, {'position': (0, 2, 0)}), (Star, {'position': (8, 4.5, 5)}), (Star, {'position': (-10, 6.5, -8)}),
                (Star, {'position': (5, 8.5, 12)}), (Star, {'position': (0, 10.5, -5)}),
                (Goomba, {'position': (3, 1, 3)}), (Goomba, {'position': (-5, 1, -2)})
            ]
        }
        # Add 'desert', 'ice', 'lava' world data here later
    }
    
    data = world_data.get(world_name, world_data['hub']) # Default to hub if world not found
    
    create_level(data['platforms'], data['color'], data['sky'])
    for obj_class, obj_kwargs in data.get('objects', []):
        entity = obj_class(**obj_kwargs)
        world_objects.append(entity)
    
    player.respawn()

# --- Initial Game Setup ---
# A dummy sound file is created if it doesn't exist, to prevent errors.
if not os.path.exists('coin_sound.wav'):
    from ursina.audio import Audio
    Audio(clip='saw', duration=0.2, pitch=-12, name='coin_sound')

ui = UI()
player = MarioController(position=(0, 5, 0))

# Load the initial world
load_world('hub')

app.run()dd
