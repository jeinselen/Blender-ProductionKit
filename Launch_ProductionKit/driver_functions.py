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



#	markerValue(required marker name, optional static or relative time, optional frames or seconds format)
#	markerValue("marker_1", False, False)
def marker_value(name, timeline=False, time=False):
	if bpy.context.scene.timeline_markers.find(name) > -1:
		scene = bpy.context.scene
		frame = scene.frame_current - scene.timeline_markers.get(name).frame if timeline else scene.timeline_markers.get(name).frame
		if time:
			return (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
		else:
			return frame
	else:
		return 0

#	markerRange(required marker start, required marker end, optional clamp at ends)
#	markerRange("mark1", "mark2", False)
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

#	markerPrev(optional text filter, optional static or relative time, optional frames or seconds format)
#	markerPrev("m", False, False)
def marker_prev(name=False, timeline=False, time=False, clamp=False):
	scene = bpy.context.scene
	frame = scene.frame_start
	
	# Find closest marker frame at or before current frame
	if len(scene.timeline_markers) > 0:
#		frame = -1000000
		for marker in scene.timeline_markers:
			if (name and name in marker.name) or not name:
				if marker.frame <= scene.frame_current and marker.frame > frame:
					frame = scene.frame_current - marker.frame if timeline else marker.frame
			else:
				frame = scene.frame_start
	
	if time:
		if clamp:
			value = (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
			return 0 if value < 0 else 1 if value > 1 else value
		else:
			return (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
	else:
		return frame

#	markerNext(optional text filter, optional static or relative time, optional frames or seconds format)
#	markerNext("m", False, False)
def marker_next(name=False, timeline=False, time=False, clamp=False):
	scene = bpy.context.scene
	frame = scene.frame_end
	
	# Find closest marker frame at or before current frame
	if len(scene.timeline_markers) > 0:
#		frame = 1000000
		for marker in scene.timeline_markers:
			if (name and name in marker.name) or not name:
				if marker.frame >= scene.frame_current and marker.frame < frame:
					frame = scene.frame_current - marker.frame if timeline else marker.frame
			else:
				frame = scene.frame_end
	
	if time:
		if clamp:
			value = (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
			return 0 if value < 0 else 1 if value > 1 else value
		else:
			return (scene.frame_current - frame) / (scene.render.fps / scene.render.fps_base)
	else:
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
		context.window_manager.clipboard = '#' + self.string
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
			
			layout.prop(settings, 'driver_select', text='')
			layout.separator()
			
			# Holding pattern for driver
			driver = ''
			
			# Error tracker
			error = ''
			
			# Curve At Time
			if settings.driver_select == 'CURVE':
				if context.active_object:
					if context.active_object.animation_data:
						layout.prop(settings, 'driver_curve_channel')
						layout.prop(settings, 'driver_curve_offset')
						
						driver = f"curveAtTime('{context.active_object.name}', {settings.driver_curve_channel}, {settings.driver_curve_offset})"
					else:
						error = 'no animation curves'
				else:
					error = 'no active object'
			
			# Marker
			elif 'MARKER-' in settings.driver_select:
				if context.scene.timeline_markers:
					# Marker Value
					if settings.driver_select == 'MARKER-VALUE':
						if settings.driver_marker_name == '':
							error = 'missing marker name'
						layout.prop_search(settings, "driver_marker_name", context.scene, "timeline_markers")
						layout.prop(settings, 'driver_marker_timeline', expand=True)
						layout.prop(settings, 'driver_marker_time', expand=True)
						
						timeline = True if settings.driver_marker_timeline == 'TIMELINE' else False
						time = True if settings.driver_marker_time == 'TIME' else False
						
						driver = f"markerValue('{settings.driver_marker_name}', {timeline}, {time})"
					
					# Marker Range
					elif settings.driver_select == 'MARKER-RANGE':
						if settings.driver_marker_name == '' or settings.driver_marker_end == '':
							error = 'missing marker name'
						layout.prop_search(settings, "driver_marker_name", context.scene, "timeline_markers")
						layout.prop_search(settings, "driver_marker_end", context.scene, "timeline_markers")
						layout.prop(settings, 'driver_marker_clamp', expand=True)
						
						clamp = True if settings.driver_marker_clamp == 'CLAMP' else False
						
						driver = f"markerRange('{settings.driver_marker_name}', '{settings.driver_marker_end}', {clamp})"
					
					# Marker Previous
					elif settings.driver_select in ['MARKER-PREV', 'MARKER-NEXT']:
						layout.prop(settings, 'driver_marker_direction', expand=True)
						layout.prop(settings, 'driver_marker_filter', expand=True)
						option = layout.row()
						if settings.driver_marker_filter == 'ALL':
							option.active = False
							option.enabled = False
						elif not len(settings.driver_marker_string) > 0:
							error = 'missing filter string'
						option.prop(settings, 'driver_marker_string')
						layout.prop(settings, 'driver_marker_timeline', expand=True)
						layout.prop(settings, 'driver_marker_time', expand=True)
						
						direction = 'markerPrev' if settings.driver_marker_direction == 'PREV' else 'markerNext'
						string = settings.driver_marker_string if settings.driver_marker_filter == 'FILTER' else ''
						timeline = True if settings.driver_marker_timeline == 'TIMELINE' else False
						time = True if settings.driver_marker_time == 'TIME' else False
						
						driver = f"{direction}('{string}', {timeline}, {time})"
				else:
					error = 'no scene markers'
				
			# Random
			elif settings.driver_select == 'RANDOM':
				layout.prop(settings, 'driver_random_min')
				layout.prop(settings, 'driver_random_max')
				layout.prop(settings, 'driver_random_seed')
				
				driver = f"random({settings.driver_random_min}, {settings.driver_random_max}, {settings.driver_random_seed})"
			
			# Wiggle
			elif settings.driver_select == 'WIGGLE':
				layout.prop(settings, 'driver_wiggle_frequency')
				layout.prop(settings, 'driver_wiggle_amplitude')
				layout.prop(settings, 'driver_wiggle_octaves')
				layout.prop(settings, 'driver_wiggle_seed')
				
				driver = f"wiggle({settings.driver_wiggle_frequency}, {settings.driver_wiggle_amplitude}, {settings.driver_wiggle_octaves}, {settings.driver_wiggle_seed})"
			
			# Copy to clipboard button
			layout.separator()
			if len(error) > 0:
				warning = layout.box()
				warning.label(text=error)
			else:
				button = layout.operator(CopyDriverToClipboard.bl_idname, text='#'+driver, icon="COPYDOWN") # COPYDOWN PASTEDOWN
				button.string = driver
		
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Driver Functions panel")



###########################################################################
# Addon registration functions

# Register custom functions in Blender's driver namespace
def production_kit_driver_functions():
	dns = bpy.app.driver_namespace
	dns["curveAtTime"] = curve_at_time
	dns["hsv"] = hsv
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
	