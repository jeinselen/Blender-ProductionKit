import bpy
from bpy.app.handlers import persistent
from colorsys import hsv_to_rgb
from mathutils import noise



#	curveAtTime(item name, animation curve index, sample time in frames)
#	curveAtTime("Cube", 0, frame-5)
#	returns the "Cube" object's first animation curve value 5 frames in the past
#	Blender requires an animation curve to get non-current-frame data
#	Blender doesn't reference animation curves by type or name, only numerical index
def curve_at_time(name, channel, frame):
	obj = bpy.data.objects[name]
	fcurve = obj.animation_data.action.fcurves[channel]
	return fcurve.evaluate(frame)



#	hsv(hue, saturation, value, output channel)
#	hsv(0.5, 1, 1, 0)
#	This will convert HSV input values into RGB output values, returning the first (red) channel
def hsv(h, s, v, c):
	color = hsv_to_rgb(h, s, v)
	if c < 0.5:
		return color[0]
	elif c < 1.5:
		return color[1]
	else:
		return color[2]



#	markerValue(marker name, frame or time)
#	markerValue("marker_1", True)
def marker_value(name, timeline=False, time=False):
	if bpy.context.scene.timeline_markers.find(name) > -1:
		frame = scene.frame_current - bpy.context.scene.timeline_markers.get(name).frame if timeline else bpy.context.scene.timeline_markers.get(name).frame
		if time:
			scene = bpy.context.scene
			return (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
		else:
			return frame
	else:
		return 0

#	markerRange(marker start, marker end)
#	markerRange("mark1", "mark2")
def marker_range(start, end, clamp=False):
	scene = bpy.context.scene
	if scene.timeline_markers.find(start) > -1 and scene.timeline_markers.find(end) > -1:
		start = scene.timeline_markers.get(start).frame
		end = scene.timeline_markers.get(end).frame
		if clamp and scene.frame_current <= start:
			return 0.0
		elif clamp and scene.frame_current >= end:
			return 1.0
		else:
			return (scene.frame_current - start) / (end - start)
	else:
		return 0

def marker_previous(timeline=False, time=False):
	# Get active scene
	scene = bpy.context.scene
	# Find closest marker frame at or before current frame
	if len(scene.timeline_markers) > 0:
		frame = -1000000
		for marker in scene.timeline_markers:
			marker_frame = marker.frame
			if marker_frame <= scene.frame_current and marker_frame > frame:
				frame = scene.frame_current - marker_frame if timeline else marker_frame
		if time:
			return (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
		else:
			return frame
	else:
		return scene.frame_start

def marker_next(timeline=False, time=False):
	# Get active scene
	scene = bpy.context.scene
	# Find closest marker frame at or before current frame
	if len(scene.timeline_markers) > 0:
		frame = 1000000
		for marker in scene.timeline_markers:
			marker_frame = marker.frame
			if marker_frame >= scene.frame_current and marker_frame < frame:
				frame = scene.frame_current - marker_frame if timeline else marker_frame
		if time:
			return (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
		else:
			return frame
	else:
		return scene.frame_end



#	random(minimum, maximum, seed)
#	markerRangeClamp(0.5, 1.5, 3575)
def random(a, b, s=-1):
	if s >= 0:
		noise.seed_set(int(s))
	return (noise.random() * (b - a)) + a



#	wiggle(speed, distance, octaves, seed)
#	wiggle(2, 1, 3, 4)
#	This is vaguely comparable to AE's 2 wiggles per second moving a distance of 1m with 3 octaves and a random seed of 4
def wiggle(freq, amp, oct, seed):
	time = bpy.context.scene.frame_current / bpy.context.scene.render.fps
	pos = (time*0.73*freq, time*0.53*freq, seed) # magic numbers to try and mimic the actually-faster-than-per-second wiggle value in AE
	return noise.fractal(pos, 1.0, 2.0, oct, noise_basis='PERLIN_ORIGINAL') * amp





###########################################################################
# Addon registration functions
			
# Register custom functions in Blender's driver namespace
def production_kit_driver_functions():
	dns = bpy.app.driver_namespace
	dns["markerValue"] = marker_value
	dns["markerRange"] = marker_range
	dns["markerPrevious"] = marker_previous
	dns["markerNext"] = marker_next
	dns["curveAtTime"] = curve_at_time
	dns["random"] = random
	dns["hsv"] = hsv
	dns["wiggle"] = wiggle

# Persistent handler to register custom functions after file load
@persistent
def load_handler(dummy):
	production_kit_driver_functions()

def register():
	production_kit_driver_functions()
#	bpy.app.handlers.load_pre.append(load_handler)
	bpy.app.handlers.load_post.append(load_handler)

def unregister():
#	if load_handler in bpy.app.handlers.load_pre:
#		bpy.app.handlers.load_pre.remove(load_handler)
	if load_handler in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(load_handler)

if __name__ == "__main__":
	register()
	