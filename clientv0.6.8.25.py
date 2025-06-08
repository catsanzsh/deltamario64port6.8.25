from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import math
import cProfile

app = Ursina()
window.title = 'Mario Platformer'
window.size = (600, 400)
window.vsync = True  # Keep vsync for smooth 60 FPS, adjustable in GPU settings
window.fps_counter.enabled = True

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
    def __init__(self):
        super().__init__()
        self.speed = 5
        self.jump_speed = 12
        self.gravity = 25
        self.velocity_y = 0
        self.grounded = False
        self.air_time = 0
        self.jump_count = 0
        self.jump_timer = 0
        self.max_jump_chain_time = 1.0
        self.running_speed = 0
        self.min_running_speed_for_long_jump = 3
        self.wall_jump_timer = 0
        self.can_wall_jump = False
        self.model = 'cube'
        self.color = color.red
        self.scale = (0.8, 1.6, 0.8)
        self.collider = 'box'
        self.camera_pivot = Entity(parent=self)
        camera.parent = self.camera_pivot
        camera.position = (0, 2, -8)
        camera.rotation_x = 10
        self.movement_input = Vec3(0, 0, 0)
        self.last_raycast_time = 0
        self.raycast_interval = 0.05  # Reduce raycast frequency

    def update(self):
        self.handle_input()
        self.update_movement()
        self.update_camera()
        self.jump_timer += time.dt
        self.wall_jump_timer += time.dt
        if self.y < -20:
            self.respawn()

    def handle_input(self):
        self.movement_input = Vec3(0, 0, 0)
        if held_keys['w'] or held_keys['up']:
            self.movement_input.z += 1
        if held_keys['s'] or held_keys['down']:
            self.movement_input.z -= 1
        if held_keys['a'] or held_keys['left']:
            self.movement_input.x -= 1
        if held_keys['d'] or held_keys['right']:
            self.movement_input.x += 1
        self.movement_input = self.movement_input.normalized()
        if held_keys['space']:
            self.jump()

    def update_movement(self):
        if self.movement_input.length() > 0:
            self.running_speed = min(self.running_speed + time.dt * 10, self.speed)
        else:
            self.running_speed = max(self.running_speed - time.dt * 8, 0)

        if self.movement_input.length() > 0:
            move_vector = self.movement_input * self.running_speed * time.dt
            camera_forward = Vec3(camera.forward.x, 0, camera.forward.z).normalized()
            camera_right = Vec3(camera.right.x, 0, camera.right.z).normalized()
            world_move = camera_forward * move_vector.z + camera_right * move_vector.x
            if not self.check_collision(world_move):
                self.position += world_move

        if not self.grounded:
            self.velocity_y -= self.gravity * time.dt
            self.air_time += time.dt

        new_y = self.y + self.velocity_y * time.dt
        if time.time - self.last_raycast_time > self.raycast_interval:
            ground_ray = raycast(self.world_position + Vec3(0, 0.1, 0), Vec3(0, -1, 0), distance=2, ignore=[self])
            self.last_raycast_time = time.time
            if ground_ray.hit and ground_ray.distance < 1.1:
                if self.velocity_y <= 0:
                    self.y = ground_ray.world_point.y + 0.8
                    if not self.grounded:
                        self.land()
                    self.grounded = True
                    self.velocity_y = 0
                    self.air_time = 0
                else:
                    self.y = new_y
            else:
                self.y = new_y
                self.grounded = False

    def jump(self):
        if self.grounded:
            if (self.jump_count < 3 and 
                self.jump_timer < self.max_jump_chain_time and 
                self.running_speed > 1):
                self.jump_count += 1
                if self.jump_count == 1:
                    self.velocity_y = self.jump_speed
                elif self.jump_count == 2:
                    self.velocity_y = self.jump_speed * 1.2
                elif self.jump_count == 3:
                    self.velocity_y = self.jump_speed * 1.5
                    self.animate_scale(1.2, duration=0.2)
                    self.animate_scale(1.0, duration=0.2, delay=0.2)
            elif self.running_speed >= self.min_running_speed_for_long_jump:
                self.velocity_y = self.jump_speed * 0.8
                forward_boost = self.movement_input * 3
                if not self.check_collision(forward_boost):
                    self.position += forward_boost
                self.jump_count = 1
            else:
                self.velocity_y = self.jump_speed
                self.jump_count = 1
            self.grounded = False
            self.jump_timer = 0
        elif self.can_wall_jump and self.wall_jump_timer > 0.1:
            self.velocity_y = self.jump_speed * 1.1
            self.position += Vec3(random.uniform(-2, 2), 0, random.uniform(-2, 2))
            self.wall_jump_timer = 0
            self.can_wall_jump = False

    def land(self):
        if self.jump_timer > self.max_jump_chain_time:
            self.jump_count = 0

    def check_collision(self, movement):
        test_pos = self.position + movement
        collision_ray = raycast(test_pos + Vec3(0, 0.5, 0), Vec3(0, -1, 0), distance=2, ignore=[self])
        wall_ray = raycast(self.world_position, movement.normalized(), distance=1.5, ignore=[self])
        if wall_ray.hit:
            self.can_wall_jump = True
            return True
        return False

    def update_camera(self):
        target_pos = self.position + Vec3(0, 2, 0)
        self.camera_pivot.position = lerp(self.camera_pivot.position, target_pos, time.dt * 3)
        if mouse.hovered_entity is None:
            self.camera_pivot.rotation_y += mouse.velocity.x * 30
            self.camera_pivot.rotation_x = max(-80, min(80, self.camera_pivot.rotation_x - mouse.velocity.y * 30))

    def respawn(self):
        if game_state.current_world == 'hub':
            self.position = (0, 2, 0)
        else:
            self.position = (0, 5, -10)

class Star(Button):
    def __init__(self, position=(0, 1, 0), **kwargs):
        super().__init__(
            parent=scene,
            model='cube',
            texture='white_cube',
            color=color.yellow,
            scale=0.5,
            position=position,
            collider='box'
        )
        self.rotation_speed = 50
        self.float_amplitude = 0.3
        self.float_speed = 2
        self.start_y = position[1]

    def update(self):
        self.rotation_y += self.rotation_speed * time.dt
        self.y = self.start_y + math.sin(time.time() * self.float_speed) * self.float_amplitude
        if distance(self, player) < 1.5:
            self.collect()

    def collect(self):
        game_state.stars += 1
        destroy(self)
        collection_effect = Entity(model='cube', color=color.gold, scale=0.8, position=self.position)
        collection_effect.animate_scale(2, duration=0.5)
        collection_effect.animate('color', color.clear, duration=0.5)
        destroy(collection_effect, delay=0.5)

class Goomba(Entity):
    def __init__(self, position=(0, 0, 0), **kwargs):
        super().__init__(
            model='cube',
            color=color.brown,
            scale=(0.8, 0.8, 0.8),
            position=position,
            collider='box'
        )
        self.move_speed = 2
        self.direction = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)).normalized()
        self.change_direction_timer = 0
        self.patrol_range = 5
        self.start_position = Vec3(position)

    def update(self):
        self.change_direction_timer += time.dt
        if (self.change_direction_timer > 3 or 
            distance(self, Entity(position=self.start_position)) > self.patrol_range):
            self.direction = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)).normalized()
            self.change_direction_timer = 0
        movement = self.direction * self.move_speed * time.dt
        if not raycast(self.position + movement + Vec3(0, 0.5, 0), Vec3(0, -1, 0), distance=2, ignore=[self]).hit:
            pass
        else:
            self.position += movement
        if distance(self, player) < 1.2 and player.y > self.y + 0.5:
            if player.velocity_y < 0:
                self.defeat()
                player.velocity_y = 8

    def defeat(self):
        defeat_effect = Entity(model='cube', color=color.orange, scale=0.5, position=self.position)
        defeat_effect.animate_scale(1.5, duration=0.3)
        defeat_effect.animate('color', color.clear, duration=0.3)
        destroy(defeat_effect, delay=0.3)
        destroy(self)

class WorldPortal(Button):
    def __init__(self, position, world_name, required_stars=0, color_theme=color.blue):
        super().__init__(
            parent=scene,
            model='cube',
            color=color_theme,
            scale=(2, 3, 1),
            position=position,
            collider='box'
        )
        self.world_name = world_name
        self.required_stars = required_stars
        self.original_color = color_theme
        self.rotation_speed = 20

    def update(self):
        self.rotation_y += self.rotation_speed * time.dt
        if distance(self, player) < 2:
            if game_state.stars >= self.required_stars:
                self.color = lerp(self.color, color.white, time.dt * 3)
                if held_keys['e']:
                    self.enter_world()
            else:
                self.color = color.gray

    def enter_world(self):
        game_state.current_world = self.world_name
        load_world(self.world_name)

class UI:
    def __init__(self):
        self.star_text = Text(f'{game_state.stars}', position=(-0.85, 0.45), scale=2, color=color.yellow)
        self.instruction_text = Text('', position=(0, -0.45), scale=1, color=color.white, origin=(0, 0))

    def update(self):
        self.star_text.text = f'{game_state.stars}'

def create_hub_world():
    clear_world()
    ground = Entity(model='cube', color=color.green, scale=(20, 1, 20), position=(0, -1, 0), collider='box')
    castle = Entity(model='cube', color=color.gray, scale=(4, 6, 4), position=(0, 2, 0), collider='box')
    portals = [
        WorldPortal((-8, 1, 5), 'grass', 0, color.green),
        WorldPortal((8, 1, 5), 'desert', 3, color.yellow),
        WorldPortal((-8, 1, -5), 'ice', 8, color.cyan),
        WorldPortal((8, 1, -5), 'lava', 15, color.red),
    ]
    for i in range(8):
        tree = Entity(model='cube', color=color.dark_green, 
                     scale=(1, 3, 1), 
                     position=(random.uniform(-15, 15), 0.5, random.uniform(-15, 15)),
                     collider='box')

def create_grass_world():
    clear_world()
    # Combine platforms into one mesh
    level_parent = Entity(model=Mesh(vertices=[], uvs=[]), color=color.green, collider='mesh')
    platform_positions = [(0, -1, 0, 15, 1, 15), (12, 2, 5, 8, 1, 8), (-10, 4, -8, 6, 1, 6), (5, 6, -12, 10, 1, 4)]
    for x, y, z, sx, sy, sz in platform_positions:
        cube = Entity(model='cube', scale=(sx, sy, sz), position=(x, y, z))
        cube.parent = level_parent
        level_parent.model.vertices.extend([Vec3(v.x * sx + x, v.y * sy + y, v.z * sz + z) for v in cube.model.vertices])
        destroy(cube)
    level_parent.model.generate()
    
    stars = [
        Star((0, 2, 0)),
        Star((12, 5, 5)),
        Star((-10, 7, -8)),
        Star((5, 9, -12)),
        Star((0, 8, 15)),
    ]
    enemies = [
        Goomba((3, 1, 3)),
        Goomba((-5, 1, -2)),
        Goomba((12, 4, 8)),
        Goomba((-8, 6, -8)),
    ]
    Entity(model='cube', color=color.purple, scale=(2, 3, 1), position=(0, 1, -12), collider='box')

def create_desert_world():
    clear_world()
    level_parent = Entity(model=Mesh(vertices=[], uvs=[]), color=color.orange, collider='mesh')
    platform_positions = [(0, -1, 0, 12, 1, 12), (15, 3, 8, 6, 1, 6), (-12, 5, -6, 8, 1, 4), (8, 8, -15, 4, 1, 8)]
    for x, y, z, sx, sy, sz in platform_positions:
        cube = Entity(model='cube', scale=(sx, sy, sz), position=(x, y, z))
        cube.parent = level_parent
        level_parent.model.vertices.extend([Vec3(v.x * sx + x, v.y * sy + y, v.z * sz + z) for v in cube.model.vertices])
        destroy(cube)
    level_parent.model.generate()
    
    pyramid1 = Entity(model='cube', color=color.yellow, scale=(3, 4, 3), position=(6, 1, 6), collider='box')
    pyramid2 = Entity(model='cube', color=color.yellow, scale=(2, 6, 2), position=(-8, 2, -3), collider='box')
    stars = [
        Star((0, 2, 0)),
        Star((15, 6, 8)),
        Star((-12, 8, -6)),
        Star((8, 11, -15)),
        Star((6, 6, 6)),
    ]
    enemies = [
        Goomba((4, 1, -4)),
        Goomba((-6, 1, 5)),
        Goomba((15, 5, 10)),
    ]

def create_ice_world():
    clear_world()
    level_parent = Entity(model=Mesh(vertices=[], uvs=[]), color=color.cyan, collider='mesh')
    platform_positions = [(0, -1, 0, 10, 1, 10), (15, 4, 10, 6, 1, 6), (-12, 7, -8, 8, 1, 5), (10, 10, -12, 5, 1, 8)]
    for x, y, z, sx, sy, sz in platform_positions:
        cube = Entity(model='cube', scale=(sx, sy, sz), position=(x, y, z))
        cube.parent = level_parent
        level_parent.model.vertices.extend([Vec3(v.x * sx + x, v.y * sy + y, v.z * sz + z) for v in cube.model.vertices])
        destroy(cube)
    level_parent.model.generate()
    
    for i in range(6):
        crystal = Entity(model='cube', color=color.light_blue, 
                        scale=(1, 2, 1),
                        position=(random.uniform(-8, 8), 1, random.uniform(-8, 8)),
                        collider='box')
    stars = [
        Star((0, 2, 0)),
        Star((15, 7, 10)),
        Star((-12, 10, -8)),
        Star((10, 13, -12)),
        Star((-5, 5, 5)),
    ]
    enemies = [
        Goomba((5, 1, -3)),
        Goomba((-4, 1, 6)),
        Goomba((15, 6, 12)),
    ]

def create_lava_world():
    clear_world()
    level_parent = Entity(model=Mesh(vertices=[], uvs=[]), color=color.dark_red, collider='mesh')
    platform_positions = [(0, -1, 0, 8, 1, 8), (12, 5, 8, 5, 1, 5), (-10, 8, -10, 6, 1, 4), (8, 12, -15, 4, 1, 6)]
    for x, y, z, sx, sy, sz in platform_positions:
        cube = Entity(model='cube', scale=(sx, sy, sz), position=(x, y, z))
        cube.parent = level_parent
        level_parent.model.vertices.extend([Vec3(v.x * sx + x, v.y * sy + y, v.z * sz + z) for v in cube.model.vertices])
        destroy(cube)
    level_parent.model.generate()
    
    lava_pool = Entity(model='cube', color=color.orange, scale=(15, 0.5, 15), position=(0, -2, 0))
    for i in range(5):
        rock = Entity(model='cube', color=color.dark_gray,
                     scale=(2, 1, 2),
                     position=(random.uniform(-12, 12), 1, random.uniform(-12, 12)),
                     collider='box')
    stars = [
        Star((0, 2, 0)),
        Star((12, 8, 8)),
        Star((-10, 11, -10)),
        Star((8, 15, -15)),
        Star((5, 3, -5)),
    ]
    enemies = [
        Goomba((6, 1, -2)),
        Goomba((-3, 1, 4)),
        Goomba((12, 7, 10)),
    ]

def clear_world():
    for entity in scene.entities.copy():
        if entity != player and not hasattr(entity, 'parent') or entity.parent != camera.ui:
            destroy(entity)

def load_world(world_name):
    if world_name == 'hub':
        create_hub_world()
        player.position = (0, 2, 0)
    elif world_name == 'grass':
        create_grass_world()
        player.position = (0, 2, -10)
    elif world_name == 'desert':
        create_desert_world()
        player.position = (0, 2, -10)
    elif world_name == 'ice':
        create_ice_world()
        player.position = (0, 2, -10)
    elif world_name == 'lava':
        create_lava_world()
        player.position = (0, 2, -10)

def input(key):
    if key == 'escape':
        quit()
    elif key == 'r':
        game_state.current_world = 'hub'
        load_world('hub')
    elif key == 'f':
        window.fullscreen = not window.fullscreen

player = MarioController()
ui = UI()
sun = DirectionalLight()
sun.look_at(Vec3(1, -1, -1))
sky = Sky(color=color.cyan)
create_hub_world()
player.position = (0, 2, 0)

def update():
    ui.update()

# Enable profiling for performance analysis
# Uncomment to run: cProfile.run("app.run()", sort="time")
app.run(info=False)
