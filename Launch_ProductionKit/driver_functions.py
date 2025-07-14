import bpy
import math
from bpy.app.handlers import persistent
from colorsys import hsv_to_rgb
from mathutils import noise

########## Easing Functions (adapted from the work of Robert Penner and https://easings.net/)

# LINEAR
def linear(t): return t

# Smoothstep and Smootherstep variations
def ease_in_smooth(t): return ease_in_out_smooth(t * 0.5) * 2.0
def ease_out_smooth(t): return ease_in_out_smooth(t * 0.5 + 0.5) * 2.0 - 1.0
def ease_in_out_smooth(t):
	return t * t * (3 - 2 * t)

def ease_in_smoothx(t): return ease_in_out_smoothx(t * 0.5) * 2.0
def ease_out_smoothx(t): return ease_in_out_smoothx(t * 0.5 + 0.5) * 2.0 - 1.0
def ease_in_out_smoothx(t):
	t = t * t * (3 - 2 * t)
	return t * t * (3 - 2 * t)

def ease_in_smoother(t): return ease_in_out_smoother(t * 0.5) * 2.0
def ease_out_smoother(t): return ease_in_out_smoother(t * 0.5 + 0.5) * 2.0 - 1.0
def ease_in_out_smoother(t):
	return t * t * t * (t * (6 * t - 15) + 10)

# SINE
def ease_in_sine(t): return 1 - math.cos((t * math.pi) / 2)
def ease_out_sine(t): return math.sin((t * math.pi) / 2)
def ease_in_out_sine(t): return -(math.cos(math.pi * t) - 1) / 2
	
# QUAD
def ease_in_quad(t): return t * t
def ease_out_quad(t): return 1 - (1 - t) * (1 - t)
def ease_in_out_quad(t):
	return 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2

# CUBIC
def ease_in_cubic(t): return t ** 3
def ease_out_cubic(t): return 1 - pow(1 - t, 3)
def ease_in_out_cubic(t):
	return 4 * t ** 3 if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2

# QUART
def ease_in_quart(t): return t ** 4
def ease_out_quart(t): return 1 - pow(1 - t, 4)
def ease_in_out_quart(t):
	return 8 * t ** 4 if t < 0.5 else 1 - pow(-2 * t + 2, 4) / 2

# QUINT
def ease_in_quint(t): return t ** 5
def ease_out_quint(t): return 1 - pow(1 - t, 5)
def ease_in_out_quint(t):
	return 16 * t ** 5 if t < 0.5 else 1 - pow(-2 * t + 2, 5) / 2

def ease_in_expo(t):
	return 0 if t == 0 else pow(2, 10 * t - 10)
def ease_out_expo(t):
	return 1 if t == 1 else 1 - pow(2, -10 * t)
def ease_in_out_expo(t):
	if t == 0: return 0
	if t == 1: return 1
	return pow(2, 20 * t - 10) / 2 if t < 0.5 else (2 - pow(2, -20 * t + 10)) / 2

# CIRC
def ease_in_circ(t): return 1 - math.sqrt(1 - t * t)
def ease_out_circ(t): return math.sqrt(1 - pow(t - 1, 2))
def ease_in_out_circ(t):
	return (1 - math.sqrt(1 - (2 * t) ** 2)) / 2 if t < 0.5 else (math.sqrt(1 - pow(-2 * t + 2, 2)) + 1) / 2

# BACK
c1 = 1.70158
c2 = c1 * 1.525
c3 = c1 + 1
def ease_in_back(t): return c3 * t * t * t - c1 * t * t
def ease_out_back(t): return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
def ease_in_out_back(t):
	if t < 0.5:
		return (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
	else:
		return (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2
	
# ELASTIC
c4 = (2 * math.pi) / 3
c5 = (2 * math.pi) / 4.5
def ease_in_elastic(t):
	if t == 0 or t == 1: return t
	return -pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4)
def ease_out_elastic(t):
	if t == 0 or t == 1: return t
	return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1
def ease_in_out_elastic(t):
	if t == 0 or t == 1: return t
	if t < 0.5:
		return -(pow(2, 20 * t - 10) * math.sin((20 * t - 11.125) * c5)) / 2
	else:
		return (pow(2, -20 * t + 10) * math.sin((20 * t - 11.125) * c5)) / 2 + 1
	
# BOUNCE
def ease_out_bounce(t):
	n1, d1 = 7.5625, 2.75
	if t < 1 / d1:
		return n1 * t * t
	elif t < 2 / d1:
		t -= 1.5 / d1
		return n1 * t * t + 0.75
	elif t < 2.5 / d1:
		t -= 2.25 / d1
		return n1 * t * t + 0.9375
	else:
		t -= 2.625 / d1
		return n1 * t * t + 0.984375
def ease_in_bounce(t): return 1 - ease_out_bounce(1 - t)
def ease_in_out_bounce(t):
	return (1 - ease_out_bounce(1 - 2 * t)) / 2 if t < 0.5 else (1 + ease_out_bounce(2 * t - 1)) / 2

# Library
easing_functions = {
	"linear": {
		"in": linear,
		"out": linear,
		"inout": linear
	},
	"smooth": {
		"in": ease_in_smooth,
		"out": ease_out_smooth,
		"inout": ease_in_out_smooth
	},
	"smoothx": {
		"in": ease_in_smoothx,
		"out": ease_out_smoothx,
		"inout": ease_in_out_smoothx
	},
	"smoother": {
		"in": ease_in_smoother,
		"out": ease_out_smoother,
		"inout": ease_in_out_smoother
	},
	"sine": {
		"in": ease_in_sine,
		"out": ease_out_sine,
		"inout": ease_in_out_sine
	},
	"quad": {
		"in": ease_in_quad,
		"out": ease_out_quad,
		"inout": ease_in_out_quad
	},
	"cubic": {
		"in": ease_in_cubic,
		"out": ease_out_cubic,
		"inout": ease_in_out_cubic
	},
	"quart": {
		"in": ease_in_quart,
		"out": ease_out_quart,
		"inout": ease_in_out_quart
	},
	"quint": {
		"in": ease_in_quint,
		"out": ease_out_quint,
		"inout": ease_in_out_quint
	},
	"expo": {
		"in": ease_in_expo,
		"out": ease_out_expo,
		"inout": ease_in_out_expo
	},
	"circ": {
		"in": ease_in_circ,
		"out": ease_out_circ,
		"inout": ease_in_out_circ
	},
	"back": {
		"in": ease_in_back,
		"out": ease_out_back,
		"inout": ease_in_out_back
	},
	"elastic": {
		"in": ease_in_elastic,
		"out": ease_out_elastic,
		"inout": ease_in_out_elastic
	},
	"bounce": {
		"in": ease_in_bounce,
		"out": ease_out_bounce,
		"inout": ease_in_out_bounce
	}
}

# Easing function for accessing all of the above from a single line
def get_ease(time, ease_type, direction):
	try:
		func = easing_functions[ease_type.lower()][direction.lower()]
		return func(time)
	except KeyError:
		raise ValueError(f"Easing not found for type='{ease_type}' and direction='{direction}'")





########## Driver Functions

#	curveAtTime(item name, animation curve index, sample time in frames)
#	curveAtTime("Cube", 0, frame-5)
#	returns the "Cube" object's first animation curve value 5 frames in the past
#	Blender requires an animation curve to get non-current-frame data
#	Blender doesn't reference animation curves by type or name, only numerical index
def curve_at_time(name, channel, frame):
	obj = bpy.data.objects[name]
	fcurve = obj.animation_data.action.fcurves[channel]
	return fcurve.evaluate(frame)



#	ease(time, type, direction)
#	ease(frame/30, circular, inout)
#	Implements common easing functions for a value between 0 and 1
#	Expected use case is within additional math expressions to map the 0-1 range to the desired values
def ease(time, ease_type, direction, a=0.0, b=1.0):
	if time <= 0.0:
		return 0.0
	elif time >= 1.0:
		return 1.0
	else:
		if a != 0.0 or b != 1.0:
			return lerp(a, b, get_ease(time, ease_type, direction))
		else:
			return get_ease(time, ease_type, direction)



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



#	lerp(value A, value B, value mix)
#	lerp(0.75, 0.25, 0.5)
#	This will mix between two values
def lerp(a, b, c):
	if c <= 0.0:
		return a
	elif c >= 1.0:
		return b
	else:
		return (a * (1.0 - c)) + (b * c)



#	markerValue(required marker name, optional static or relative time, optional frames or seconds format)
#	markerValue("marker_1", False, False)
def marker_value(name, relative=False, seconds=False, clamp=False, duration=1):
	scene = bpy.context.scene
	frame = 0
	if scene.timeline_markers.find(name) > -1:
		frame = scene.timeline_markers.get(name).frame
		if relative:
			frame = scene.frame_current - frame
		if seconds:
			frame /= scene.render.fps / scene.render.fps_base
			if clamp:
				frame = min(max(frame/duration, 0), 1)
	return frame

#	markerRange(required marker start, required marker end, optional clamp at ends, optional start value, optional end value)
#	markerRange("marker_1", "marker_2", False, 0.0, 1.0)
def marker_range(start, end, clamp=False, a=0.0, b=1.0, ease_type='linear', direction='inout'):
	scene = bpy.context.scene
	if scene.timeline_markers.find(start) > -1 and scene.timeline_markers.find(end) > -1:
		start = scene.timeline_markers.get(start).frame
		end = scene.timeline_markers.get(end).frame
		if clamp and scene.frame_current <= start:
			return a
		elif clamp and scene.frame_current >= end:
			return b
		else:
			c = (scene.frame_current - start) / (end - start)
			if clamp and ease_type != 'linear':
				c = get_ease(c, ease_type, direction)
			return (a * (1.0 - c)) + (b * c)
	else:
		return 0.0

#	markerPrev(optional text filter, optional static or relative time, optional frames or seconds format)
def marker_prev(name=False, relative=False, seconds=False, clamp=False, duration=1):
	scene = bpy.context.scene
	frame = scene.frame_start
	# Find closest marker frame at or before current frame
	if len(scene.timeline_markers) > 0:
		frame = -100000
		marker_found = False
		for marker in scene.timeline_markers:
			if (name and name in marker.name) or not name:
				marker_found = True
				if marker.frame <= scene.frame_current and marker.frame > frame:
					frame = marker.frame
		if not marker_found:
			frame = scene.frame_start
	if relative:
		frame = scene.frame_current - frame
	if seconds:
		frame /= scene.render.fps / scene.render.fps_base
		if clamp:
			frame = min(max(frame/duration, 0), 1)
	return frame

#	markerNext(optional text filter, optional static or relative time, optional frames or seconds format)
def marker_next(name=False, relative=False, seconds=False, clamp=False, duration=1):
	scene = bpy.context.scene
	frame = scene.frame_end
	# Find closest marker frame at or before current frame
	if len(scene.timeline_markers) > 0:
		frame = 100000
		marker_found = False
		for marker in scene.timeline_markers:
			if (name and name in marker.name) or not name:
				marker_found = True
				if marker.frame >= scene.frame_current and marker.frame < frame:
					frame = scene.frame_current - marker.frame if relative else marker.frame
		if not marker_found:
			frame = scene.frame_end
	if relative:
		frame = scene.frame_current - frame
	if seconds:
		frame /= scene.render.fps / scene.render.fps_base
		if clamp:
			frame = min(max(frame/duration, 0), 1)
	return frame



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
# UI rendering class

class CopyDriverToClipboard(bpy.types.Operator):
	"""Copy the specified string to the clipboard"""
	bl_idname = "object.copy_to_clipboard"
	bl_label = "Copy Text"
	
	string: bpy.props.StringProperty(default="")
	
	def execute(self, context):
		context.window_manager.clipboard = self.string
		return {'FINISHED'}

class PRODUCTIONKIT_PT_driverFunctions(bpy.types.Panel):
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = 'Launch'
	bl_order = 4
	bl_options = {'DEFAULT_CLOSED'}
	bl_label = "Driver Functions"
	bl_idname = "PRODUCTIONKIT_PT_driverFunctions"
	
	@classmethod
	def poll(cls, context):
		return True # context.active_object
	
	def draw_header(self, context):
		try:
			layout = self.layout
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Driver Functions panel header")
	
	def draw(self, context):
		settings = context.scene.production_kit_settings
		try:
			layout = self.layout
			layout.use_property_decorate = False # No animation
			
			col = layout.column(align=True)
			col.prop(settings, 'driver_select', text='')
			
			# Driver string
			driver = ''
			
			# Error tracker
			error = ''
			
			# Curve At Time
			if settings.driver_select == 'CURVE':
				if context.active_object:
					obj = context.active_object
					if obj.animation_data and obj.animation_data.action and obj.animation_data.action.fcurves:
						col.prop(settings, 'driver_curve_channel')
						col.prop(settings, 'driver_curve_offset')
						
						driver = f"curveAtTime('{context.active_object.name}', {settings.driver_curve_channel}, {settings.driver_curve_offset})"
					else:
						error = 'no animation curves'
				else:
					error = 'no active object'
			
			# Ease
			if settings.driver_select == 'EASE':
				row1 = col.row(align=True)
				row1.prop(settings, 'driver_value_t', text='')
				row1.prop(settings, 'driver_ease_type', text='')
				row1.prop(settings, 'driver_ease_direction', text='')
				
				driver = f"ease({settings.driver_value_t}, '{settings.driver_ease_type}', '{settings.driver_ease_direction}')"
			
			# Lerp
			if settings.driver_select == 'LERP':
				row1 = col.row(align=True)
				row1.prop(settings, 'driver_value_a')
				row1.prop(settings, 'driver_value_b')
				row1.prop(settings, 'driver_value_c')
				
				driver = f"lerp({settings.driver_value_a}, {settings.driver_value_b}, {settings.driver_value_c})"
			
			# Marker
			elif 'MARKER-' in settings.driver_select:
				if context.scene.timeline_markers:
					relative = True if settings.driver_marker_relative == 'RELATIVE' else False
					seconds = True if settings.driver_marker_seconds == 'SECONDS' else False
					clamp = True if settings.driver_marker_clamp == 'CLAMP' else False
					duration = settings.driver_marker_duration
					
					# Marker Value
					if settings.driver_select == 'MARKER-VALUE':
						col.prop_search(settings, "driver_marker_name", context.scene, "timeline_markers", text="")
						col.separator()
						
						row1 = col.row(align=True)
						row1.prop(settings, 'driver_marker_relative', expand=True)
						row2 = col.row(align=True)
						row2.prop(settings, 'driver_marker_seconds', expand=True)
						row3 = col.row(align=True)
						if not (relative and seconds):
							row3.active = False
							row3.enabled = False
							duration = 1
						row3.prop(settings, 'driver_marker_clamp', expand=True)
						row3.prop(settings, 'driver_marker_duration', text='')
						
						if settings.driver_marker_name == '':
							error = 'missing marker name'
						else:
							driver = f"markerValue('{settings.driver_marker_name}', {relative}, {seconds}, {clamp}, {duration})"
					
					# Marker Range
					elif settings.driver_select == 'MARKER-RANGE':
						col.prop_search(settings, "driver_marker_name", context.scene, "timeline_markers", text="")
						col.prop_search(settings, "driver_marker_end", context.scene, "timeline_markers", text="")
						row1 = col.row()
						row1.prop(settings, 'driver_marker_clamp', expand=True)
						row2 = col.row(align=True)
						row2a = row2.row(align=True)
						row2a.prop(settings, 'driver_value_a', text="")
						row2a.prop(settings, 'driver_value_b', text="")
						row2b = row2.row(align=True)
						if settings.driver_marker_clamp != "CLAMP":
							row2b.active = False
							row2b.enabled = False
						row2b.prop(settings, 'driver_ease_type', text="")
						row2b.prop(settings, 'driver_ease_direction', text="")
						
						if settings.driver_marker_name == '' or settings.driver_marker_end == '':
							error = 'missing marker name'
						elif settings.driver_marker_name == settings.driver_marker_end:
							error = 'duplicate marker name'
						else:
							driver = f"markerRange('{settings.driver_marker_name}', '{settings.driver_marker_end}'"
							clamp = True if settings.driver_marker_clamp == "CLAMP" else False
							valueA = settings.driver_value_a
							valueB =settings.driver_value_b
							easeType = settings.driver_ease_type
							easeDirection = settings.driver_ease_direction
							if settings.driver_marker_clamp == "CLAMP":
								driver += f", {clamp}"
								if valueA != 0.0 or valueB != 1.0 or easeType != "linear":
									driver += f", {valueA}, {valueB}"
								if easeType != "linear":
									driver += f", '{easeType}', '{easeDirection}'"
							driver += ")"
					
					# Marker Previous
					elif settings.driver_select in ['MARKER-PREV', 'MARKER-NEXT']:
						row1 = col.row(align=True)
						row1.prop(settings, 'driver_marker_filter', expand=True)
						option = col.row(align=True)
						if settings.driver_marker_filter == 'ALL':
							option.active = False
							option.enabled = False
						option.prop(settings, 'driver_marker_string', text='')
						col.separator()
						
						row2 = col.row(align=True)
						row2.prop(settings, 'driver_marker_relative', expand=True)
						row3 = col.row(align=True)
						row3.prop(settings, 'driver_marker_seconds', expand=True)
						options = col.row(align=True)
						if not (relative and seconds):
							options.active = False
							options.enabled = False
							duration = 1
						options.prop(settings, 'driver_marker_clamp', expand=True)
						options.prop(settings, 'driver_marker_duration', text='')
						
						direction = 'markerPrev' if settings.driver_select == 'MARKER-PREV' else 'markerNext'
						string = settings.driver_marker_string if settings.driver_marker_filter == 'FILTER' else ''
						
						if len(settings.driver_marker_string) == 0:
							error = 'missing filter string'
						else:
							driver = f"{direction}('{string}', {relative}, {seconds}, {clamp}, {duration})"
				else:
					error = 'no scene markers'
			
			# Random
			elif settings.driver_select == 'RANDOM':
				col.prop(settings, 'driver_random_min')
				col.prop(settings, 'driver_random_max')
				col.prop(settings, 'driver_random_seed')
				
				driver = f"random({settings.driver_random_min}, {settings.driver_random_max}, {settings.driver_random_seed})"
			
			# Wiggle
			elif settings.driver_select == 'WIGGLE':
				col.prop(settings, 'driver_wiggle_frequency')
				col.prop(settings, 'driver_wiggle_amplitude')
				col.prop(settings, 'driver_wiggle_octaves')
				col.prop(settings, 'driver_wiggle_seed')
				
				driver = f"wiggle({settings.driver_wiggle_frequency}, {settings.driver_wiggle_amplitude}, {settings.driver_wiggle_octaves}, {settings.driver_wiggle_seed})"
			
			# Copy to clipboard button
			layout.separator()
			button = layout.row()
			text = '#' + driver
			icon = 'COPYDOWN' # COPYDOWN PASTEDOWN
			if len(error) > 0:
				text = error
				icon = 'ERROR' # ERROR CANCEL
				button.active = False
				button.enabled = False
			ops = button.operator(CopyDriverToClipboard.bl_idname, text=text, icon=icon)
			ops.string = text
		
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Driver Functions panel")



###########################################################################
# Addon registration functions

# Register custom functions in Blender's driver namespace
def production_kit_driver_functions():
	dns = bpy.app.driver_namespace
	dns["curveAtTime"] = curve_at_time
	dns["ease"] = ease
	dns["hsv"] = hsv
	dns["lerp"] = lerp
#	dns["mix"] = lerp
	dns["markerValue"] = marker_value
	dns["markerRange"] = marker_range
	dns["markerPrev"] = marker_prev
	dns["markerNext"] = marker_next
	dns["random"] = random
	dns["wiggle"] = wiggle

# Persistent handler to register custom functions after file load
@persistent
def load_handler(dummy):
	production_kit_driver_functions()

classes = (CopyDriverToClipboard, PRODUCTIONKIT_PT_driverFunctions)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	production_kit_driver_functions()
#	bpy.app.handlers.load_pre.append(load_handler)
	bpy.app.handlers.load_post.append(load_handler)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
#	if load_handler in bpy.app.handlers.load_pre:
#		bpy.app.handlers.load_pre.remove(load_handler)
	if load_handler in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(load_handler)

if __name__ == "__main__":
	register()
	