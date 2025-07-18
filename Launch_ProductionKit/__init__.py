import bpy
import os

# FFmpeg system access
from shutil import which

# Local imports
from . import audio_waveforms
from .color_palette import ColorPaletteProperty, AddColorOperator, RemoveColorOperator, ReorderColorOperator, CopyColorOperator, EditPaletteOperator, SavePaletteOperator, LoadPaletteOperator, PRODUCTIONKIT_PT_colorPalette
from . import cycle_transforms
from . import driver_functions
from . import transfer_to_scene
from .project_version import PRODUCTIONKIT_OT_SaveProjectVersion, TOPBAR_MT_file_save_version
from .update_images import Production_Kit_Update_Images, Production_Kit_Switch_Extension_Inputs, Production_Kit_Replace_Extensions, PRODUCTIONKIT_PT_update_images_ui, production_kit_update_images_menu_item
from . import vertex_locations
from .viewport_shading import PRODUCTIONKIT_OT_set_viewport_shading, production_kit_viewport_shading_menu_items



###########################################################################
# Global user preferences and UI rendering class

class ProductionKitPreferences(bpy.types.AddonPreferences):
	bl_idname = __package__
	
	########## Project Version ##########
	
	version_type: bpy.props.EnumProperty(
		name='Type',
		description='Version file naming convention',
		items=[
			('NUM', 'Number', 'Save versions using autogenerated serial numbers'),
			('TIME', 'Timestamp', 'Save versions with the current date and time'),
			('ALPHANUM', 'Alphanumeric', 'Save versions with an incrementing major version number and minor alphabet character')
			],
		default='NUM')
	version_path: bpy.props.StringProperty(
		name="Path",
		description="Leave a single forward slash to auto generate folders alongside project files",
		default="//_Archive",
		maxlen=4096,
		subtype="DIR_PATH")
	version_separator: bpy.props.StringProperty(
		name="Separator",
		description="separator between the project name and the version number",
		default="-",
		maxlen=16)
	version_length: bpy.props.IntProperty(
		name="Characters",
		description="Total character count, padded with leading zeroes",
		default=4,
		soft_min=1,
		soft_max=8,
		min=1,
		max=8)
	version_compress: bpy.props.BoolProperty(
		name='Compression',
		description='Compresses versioned files, or for Alphanumeric, compresses the main project when saving',
		default=True)
	version_keepbackup: bpy.props.BoolProperty(
		name='Keep .blend1',
		description='Keeps the .blend1 backup file alongside the archived project',
		default=False)
	version_popup: bpy.props.BoolProperty(
		name='Success Popup',
		description='Confirms successful version saving with a popup panel',
		default=False)
	version_auto: bpy.props.BoolProperty(
		name='Detect Alphanumeric',
		description='Recognises if the current project file already has an alphanumeric serial number, and uses that versioning type automatically',
		default=True)
	
	
	
	########## Update Images ##########
	
	# Global variables
	enable_file_reload: bpy.props.BoolProperty(
		name="File Reload",
		description="Reloads all image files",
		default=True)
	enable_file_format: bpy.props.BoolProperty(
		name="File Format",
		description="Formats all image files using the specified filters",
		default=False)
	
	# Filter sets (this should really use a dynamic list, not static presets)
	filter1_name: bpy.props.StringProperty(
		name="Filter Name",
		description="String to match in the image name",
		default="-color",
		maxlen=4096)
	filter1_colorspace: bpy.props.EnumProperty(
		name='Color Space',
		description='Set matching files to this color space',
		items=[
			('Filmic Log', 'Filmic Log', 'Filmic Log color space'),
			('Linear', 'Linear', 'Linear color space'),
			('Linear ACES', 'Linear ACES', 'Linear ACES color space'),
			('Linear ACEScg', 'Linear ACEScg', 'Linear ACEScg color space'),
			('Non-Color', 'Non-Color', 'Non-Color color space'),
			('Raw', 'Raw', 'Raw color space'),
			('sRGB', 'sRGB', 'sRGB color space'),
			('XYZ', 'XYZ', 'XYZ color space')
			],
		default='sRGB')
	filter1_alphamode: bpy.props.EnumProperty(
		name='Alpha Mode',
		description='Set matching files to this alpha mode',
		items=[
			('STRAIGHT', 'Straight', 'RGB channels are stored without association, but the alpha still operates as a mask'),
			('PREMUL', 'Premultiplied', 'RGB channels have been multiplied by the alpha'),
			('CHANNEL_PACKED', 'Channel Packed', 'Treat alpha as a fourth color channel without masking'),
			('NONE', 'None', 'Ignore alpha channel')
			],
		default='STRAIGHT')

	filter2_name: bpy.props.StringProperty(
		name="Filter Name",
		description="String to match in the image name",
		default="-orm",
		maxlen=4096)
	filter2_colorspace: bpy.props.EnumProperty(
		name='Color Space',
		description='Set matching files to this color space',
		items=[
			('Filmic Log', 'Filmic Log', 'Filmic Log color space'),
			('Linear', 'Linear', 'Linear color space'),
			('Linear ACES', 'Linear ACES', 'Linear ACES color space'),
			('Linear ACEScg', 'Linear ACEScg', 'Linear ACEScg color space'),
			('Non-Color', 'Non-Color', 'Non-Color color space (typically used for normal maps)'),
			('Raw', 'Raw', 'Raw color space'),
			('sRGB', 'sRGB', 'sRGB color space'),
			('XYZ', 'XYZ', 'XYZ color space')
			],
		default='Non-Color')
	filter2_alphamode: bpy.props.EnumProperty(
		name='Alpha Mode',
		description='Set matching files to this alpha mode',
		items=[
			('STRAIGHT', 'Straight', 'RGB channels are stored without association, but the alpha channel still operates as a mask'),
			('PREMUL', 'Premultiplied', 'RGB channels have been multiplied by the alpha channel as an embedded mask'),
			('CHANNEL_PACKED', 'Channel Packed', 'Treat the alpha as a fourth color channel without masking'),
			('NONE', 'None', 'Ignore alpha channel')
			],
		default='CHANNEL_PACKED')

	filter3_name: bpy.props.StringProperty(
		name="Filter Name",
		description="String to match in the image name",
		default="-normal",
		maxlen=4096)
	filter3_colorspace: bpy.props.EnumProperty(
		name='Color Space',
		description='Set matching files to this color space',
		items=[
			('Filmic Log', 'Filmic Log', 'Filmic Log color space'),
			('Linear', 'Linear', 'Linear color space'),
			('Linear ACES', 'Linear ACES', 'Linear ACES color space'),
			('Linear ACEScg', 'Linear ACEScg', 'Linear ACEScg color space'),
			('Non-Color', 'Non-Color', 'Non-Color color space (typically used for normal maps)'),
			('Raw', 'Raw', 'Raw color space'),
			('sRGB', 'sRGB', 'sRGB color space'),
			('XYZ', 'XYZ', 'XYZ color space')
			],
		default='Non-Color')
	filter3_alphamode: bpy.props.EnumProperty(
		name='Alpha Mode',
		description='Set matching files to this alpha mode',
		items=[
			('STRAIGHT', 'Straight', 'RGB channels are stored without association, but the alpha channel still operates as a mask'),
			('PREMUL', 'Premultiplied', 'RGB channels have been multiplied by the alpha channel as an embedded mask'),
			('CHANNEL_PACKED', 'Channel Packed', 'Treat the alpha as a fourth color channel without masking'),
			('NONE', 'None', 'Ignore alpha channel')
			],
		default='CHANNEL_PACKED')

	filter4_name: bpy.props.StringProperty(
		name="Filter Name",
		description="String to match in the image name",
		default="",
		maxlen=4096)
	filter4_colorspace: bpy.props.EnumProperty(
		name='Color Space',
		description='Set matching files to this color space',
		items=[
			('Filmic Log', 'Filmic Log', 'Filmic Log color space'),
			('Linear', 'Linear', 'Linear color space'),
			('Linear ACES', 'Linear ACES', 'Linear ACES color space'),
			('Linear ACEScg', 'Linear ACEScg', 'Linear ACEScg color space'),
			('Non-Color', 'Non-Color', 'Non-Color color space (typically used for normal maps)'),
			('Raw', 'Raw', 'Raw color space'),
			('sRGB', 'sRGB', 'sRGB color space'),
			('XYZ', 'XYZ', 'XYZ color space')
			],
		default='sRGB')
	filter4_alphamode: bpy.props.EnumProperty(
		name='Alpha Mode',
		description='Set matching files to this alpha mode',
		items=[
			('STRAIGHT', 'Straight', 'RGB channels are stored without association, but the alpha channel still operates as a mask'),
			('PREMUL', 'Premultiplied', 'RGB channels have been multiplied by the alpha channel as an embedded mask'),
			('CHANNEL_PACKED', 'Channel Packed', 'Treat the alpha as a fourth color channel without masking'),
			('NONE', 'None', 'Ignore alpha channel')
			],
		default='STRAIGHT')

	filter5_name: bpy.props.StringProperty(
		name="Filter Name",
		description="String to match in the image name",
		default="",
		maxlen=4096)
	filter5_colorspace: bpy.props.EnumProperty(
		name='Color Space',
		description='Set matching files to this color space',
		items=[
			('Filmic Log', 'Filmic Log', 'Filmic Log color space'),
			('Linear', 'Linear', 'Linear color space'),
			('Linear ACES', 'Linear ACES', 'Linear ACES color space'),
			('Linear ACEScg', 'Linear ACEScg', 'Linear ACEScg color space'),
			('Non-Color', 'Non-Color', 'Non-Color color space (typically used for normal maps)'),
			('Raw', 'Raw', 'Raw color space'),
			('sRGB', 'sRGB', 'sRGB color space'),
			('XYZ', 'XYZ', 'XYZ color space')
			],
		default='sRGB')
	filter5_alphamode: bpy.props.EnumProperty(
		name='Alpha Mode',
		description='Set matching files to this alpha mode',
		items=[
			('STRAIGHT', 'Straight', 'RGB channels are stored without association, but the alpha channel still operates as a mask'),
			('PREMUL', 'Premultiplied', 'RGB channels have been multiplied by the alpha channel as an embedded mask'),
			('CHANNEL_PACKED', 'Channel Packed', 'Treat the alpha as a fourth color channel without masking'),
			('NONE', 'None', 'Ignore alpha channel')
			],
		default='STRAIGHT')
	
	
	
	########## Audio Waveforms ##########
	
	waveform_size_x: bpy.props.IntProperty(
		name="Waveform Size X",
		description="Horizontal resolution multiplier",
		default=2,
		soft_min=1,
		soft_max=4,
		min=1,
		max=8)
	waveform_size_y: bpy.props.IntProperty(
		name="Waveform Size Y",
		description="Total vertical resolution",
		default=128,
		soft_min=64,
		soft_max=256,
		min=16,
		max=1024)
	waveform_display_sampling: bpy.props.EnumProperty(
		name='Waveform sampling',
		description='Set oversampling detail',
		items=[
			('1', 'No sampling', 'No oversampling'),
			('2', 'x2', 'Two times oversampling'),
			('3', 'x3', 'Three times oversampling'),
			('4', 'x4', 'Four times oversampling')
			],
		default='1')
	waveform_display_color: bpy.props.FloatVectorProperty(
		name="Color",
		subtype='COLOR',
		size=4,
		default=(1.0, 1.0, 1.0, 0.2),
		min=0.0,
		max=1.0)
	waveform_display_scale: bpy.props.FloatProperty(
		name="Scale",
		default=0.5,
		soft_min=0.2,
		soft_max=2.0,
		min=0.02,
		max=20.0)
	waveform_display_offset: bpy.props.FloatProperty(
		name="Offset",
		default=0.5,
		soft_min=0.0,
		soft_max=1.0,
		min=-1.0,
		max=2.0)
	
	ffmpeg_processing: bpy.props.BoolProperty(
		name='Enable Waveform Display',
		description='Enables audio waveform generation using FFmpeg and turns on the drop track UI panel',
		default=True)
	ffmpeg_location: bpy.props.StringProperty(
		name="FFmpeg location",
		description="System location where the the FFmpeg command line interface is installed",
		default="/opt/local/bin/ffmpeg",
		maxlen=4096,
		update=lambda self, context: self.check_ffmpeg_location())
	ffmpeg_location_previous: bpy.props.StringProperty(default="")
	ffmpeg_exists: bpy.props.BoolProperty(
		name="FFmpeg exists",
		description='Stores the existence of FFmpeg at the defined system location',
		default=False)
	
	# Validate the ffmpeg location string on value change and plugin registration
	def check_ffmpeg_location(self):
		# Ensure it points at ffmpeg
		if not self.ffmpeg_location.endswith('ffmpeg'):
			self.ffmpeg_location = self.ffmpeg_location + 'ffmpeg'
		# Test if it's a valid path and replace with valid path if such exists
		if self.ffmpeg_location != self.ffmpeg_location_previous:
			if which(self.ffmpeg_location) is None:
				if which("ffmpeg") is None:
					self.ffmpeg_exists = False
				else:
					self.ffmpeg_location = which("ffmpeg")
					self.ffmpeg_exists = True
			else:
				self.ffmpeg_exists = True
			self.ffmpeg_location_previous = self.ffmpeg_location
	
	
	
	########## Colour Palette ##########
	
	def update_palette_category(self, context):
		category = bpy.context.preferences.addons[__package__].preferences.palette_category
		try:
			bpy.utils.unregister_class(PRODUCTIONKIT_PT_colorPalette)
		except RuntimeError:
			pass
		if len(category) > 0:
			PRODUCTIONKIT_PT_colorPalette.bl_category = category
			bpy.utils.register_class(PRODUCTIONKIT_PT_colorPalette)
	
	palette_category: bpy.props.StringProperty(
		name="Palette Panel",
		description="Choose a category for the panel to be placed in",
		default="Launch",
		update=update_palette_category)
		# Consider adding search_options=(list of currently available tabs) for easier operation
	palette_file_location: bpy.props.StringProperty(
		name = "Palette Location",
		description = "Location of the palette library saved alongside the project file (should always be a relative path)",
		default = "//",
		maxlen = 4096,
		subtype = "DIR_PATH")
	palette_file_name: bpy.props.StringProperty(
		name = "Palette Name",
		description = "Name of the plain text library file",
		default = "ProductionKit-Palette.txt",
		maxlen = 1024)
	
	
	
	########## Driver Functions ##########
	
	def update_drivers_category(self, context):
		category = bpy.context.preferences.addons[__package__].preferences.drivers_category
		try:
			bpy.utils.unregister_class(driver_functions.PRODUCTIONKIT_PT_driverFunctions)
		except RuntimeError:
			pass
		if len(category) > 0:
			driver_functions.PRODUCTIONKIT_PT_driverFunctions.bl_category = category
			bpy.utils.register_class(driver_functions.PRODUCTIONKIT_PT_driverFunctions)
			
	drivers_category: bpy.props.StringProperty(
		name="Keyframes Panel",
		description="Choose a category for the panel to be placed in",
		default="Launch",
		update=update_drivers_category)
		# Consider adding search_options=(list of currently available tabs) for easier operation
	
	
	
	########## Vertex Location Keyframes ##########
	
	def update_keyframes_category(self, context):
		category = bpy.context.preferences.addons[__package__].preferences.keyframes_category
		try:
			bpy.utils.unregister_class(vertex_locations.PRODUCTIONKIT_PT_vertexLocation)
		except RuntimeError:
			pass
		if len(category) > 0:
			vertex_locations.PRODUCTIONKIT_PT_vertexLocation.bl_category = category
			bpy.utils.register_class(vertex_locations.PRODUCTIONKIT_PT_vertexLocation)
	
	keyframes_category: bpy.props.StringProperty(
		name="Keyframes Panel",
		description="Choose a category for the panel to be placed in",
		default="Launch",
		update=update_keyframes_category)
		# Consider adding search_options=(list of currently available tabs) for easier operation
	
	
	
	############################## Preferences UI ##############################
	
	# User Interface
	def draw(self, context):
		settings = context.scene.production_kit_settings
		
		layout = self.layout
		
		########## Project Version ##########
		
		layout.label(text="Save Project Version", icon="FILE") # FILE CURRENT_FILE FILE_BLEND DUPLICATE
		
		# Alignment Column
		col = layout.column(align=True)
		
		# Create Info Strings
		if self.version_type == 'ALPHANUM':
			info = 'Saves project with new name, archives previous file'
			info_file = 'ProjectName' + self.version_separator
			version_length = format(self.version_length - 1, '02')
			info_file += format(1, version_length) + "b.blend,    " + self.version_path + '...' + format(1, version_length) + 'a.blend'
		else:
			info = 'Copies project to archive with '
			info_file = os.path.join(self.version_path, 'ProjectName') + self.version_separator
			if self.version_type == 'TIME':
				info += 'date and time'
				info_file += 'YYYY-MM-DD-HH-MM-SS'
			else:
				info += 'automatic serial number'
				version_length = format(self.version_length, '02')
				info_file += format(1, version_length)
			info_file += '.blend'
			
		# Display Info
		box = col.box()
		col2 = box.column(align=True)
		col2.label(text=info)
		col2.label(text=info_file)
		
		# Versioning Type
		row = col.row(align=True)
		row.prop(self, 'version_type', expand=True)
		
		# Path Location
		col.prop(self, "version_path", text='')
		
		# Naming Options
		row = col.row(align=True)
		row.prop(self, "version_separator", text='')
		if self.version_type != 'TIME':
			row.prop(self, "version_length")
		
		# Settings Checkboxes
		grid0 = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=False)
		grid0.prop(self, "version_compress")
		grid0.prop(self, "version_popup")
		grid0.prop(self, "version_auto")
		if self.version_type == 'ALPHANUM' or self.version_auto:
			grid0.prop(self, "version_keepbackup")
		
		
		
		########## Update Images ##########
		
		layout.separator(factor = 2.0)
		layout.label(text="Update Image Files", icon="IMAGE") # IMAGE IMAGE_DATA FILE_IMAGE NODE_TEXTURE
		
		grid1 = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=False)
		grid1.prop(self, "enable_file_reload")
		grid1.prop(self, "enable_file_format")
		
		grid = layout.grid_flow(row_major=True, columns=2, even_columns=False, even_rows=False, align=False)
		if not self.enable_file_format:
			grid.enabled = False
		
		grid.prop(self, "filter1_name", text='')
		row1 = grid.row(align=False)
		if not self.filter1_name:
			row1.enabled = False
		row1.prop(self, "filter1_colorspace", text='')
		row1.prop(self, "filter1_alphamode", text='')
		
		grid.prop(self, "filter2_name", text='')
		row2 = grid.row(align=False)
		if not self.filter2_name:
			row2.enabled = False
		row2.prop(self, "filter2_colorspace", text='')
		row2.prop(self, "filter2_alphamode", text='')
		
		grid.prop(self, "filter3_name", text='')
		row3 = grid.row(align=False)
		if not self.filter3_name:
			row3.enabled = False
		row3.prop(self, "filter3_colorspace", text='')
		row3.prop(self, "filter3_alphamode", text='')
		
		grid.prop(self, "filter4_name", text='')
		row4 = grid.row(align=False)
		if not self.filter4_name:
			row4.enabled = False
		row4.prop(self, "filter4_colorspace", text='')
		row4.prop(self, "filter4_alphamode", text='')
		
		grid.prop(self, "filter5_name", text='')
		row5 = grid.row(align=False)
		if not self.filter5_name:
			row5.enabled = False
		row5.prop(self, "filter5_colorspace", text='')
		row5.prop(self, "filter5_alphamode", text='')
		
		
		
		########## Audio Waveform ##########
		
		layout.separator(factor = 2.0)
		layout.label(text="Audio Waveform", icon="COLOR") # COLOR
		
		grid2 = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=False)
		grid2.prop(self, "ffmpeg_processing")
		input = grid2.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=False)
		if not self.ffmpeg_processing:
			input.active = False
			input.enabled = False
		input.prop(self, "ffmpeg_location", text="")
		# Location exists success/fail
		if self.ffmpeg_exists:
			input.label(text="✔︎ installed")
		else:
			input.label(text="✘ missing")
		grid2.separator()
		input = grid2.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=False)
		if not self.ffmpeg_processing:
			input.active = False
			input.enabled = False
		input.prop(self, "waveform_display_sampling", text="", icon="ALIASED") # ALIASED ANTIALIASED SHARPCURVE
		input.prop(self, "waveform_display_color", text="", icon="MOD_TINT") # MOD_TINT COLOR RESTRICT_COLOR_OFF RESTRICT_COLOR_ON
		
		
		
		########## Colour Palette ##########
		
		layout.separator(factor = 2.0)
		layout.label(text="Color Palette", icon="COLOR") # COLOR RESTRICT_COLOR_ON RESTRICT_COLOR_OFF
		
		grid3 = layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=False, align=False)
		grid3.prop(self, "palette_file_location", text='')
		grid3.prop(self, "palette_file_name", text='')
		grid3.prop(self, "palette_category", text='')
		
		
		
		########## Vertex Location Keyframes ##########
		
		layout.separator(factor = 2.0)
		layout.label(text="Vertex Location Keyframes", icon="DECORATE_KEYFRAME") # GROUP_VERTEX VERTEXSEL DECORATE_KEYFRAME KEYFRAME_HLT KEYFRAME
		layout.prop(self, "keyframes_category", text='Sidebar Tab')



###########################################################################
# Local project settings

class ProductionKitSettings(bpy.types.PropertyGroup):
	
	########## Update Images ##########
	
	file_extension_source: bpy.props.StringProperty(
		name="Source File Extension",
		description="Define the file extension you want to replace",
		default=".png",
		maxlen=4096)
	file_extension_target: bpy.props.StringProperty(
		name="Target File Extension",
		description="Replace all source file extensions with this file extension",
		default=".jpg",
		maxlen=4096)
	
	########## Colour Palette ##########
	
	palette_edit: bpy.props.BoolProperty(
		name = "Editing Status",
		description = "Editing status of the palette",
		default = False)
	
	########## Driver Functions ##########
	
	driver_select: bpy.props.EnumProperty(
		name='Driver',
		description='List of available driver functions',
		items=[
			('CURVE', 'Curve at Time', 'Value from curve at specified time or time offset'),
			('EASE', 'Ease', 'Calculates easing curves between 0 and 1'),
			('LERP', 'Lerp Values', 'Linearly interpolate (mix) between two values using a third value'),
			('MARKER-VALUE', 'Marker Value', 'Value of named marker'),
			('MARKER-RANGE', 'Marker Range', '0-1 value range between two named markers'),
			('MARKER-PREV', 'Marker Previous', 'Value of nearest marker before the current frame'),
			('MARKER-NEXT', 'Marker Next', 'Value of nearest marker after the current frame'),
			('RANDOM', 'Random', 'Value randomisation'),
			('WIGGLE', 'Wiggle', 'Value noise pattern'),
			],
		default='CURVE')
	
	# Curve at Time (object name will be taken from whatever object is currently active)
#	driver_curve_channel: bpy.props.IntProperty(
#		name="Property",
#		default=0)
	
	driver_curve_channel: bpy.props.EnumProperty(
		name="Property",
		items=lambda self, context: self.get_fcurve_items(context)
	)
	
	def get_fcurve_items(self, context):
		items = []
		if context.active_object:
			obj = context.active_object
			if obj.animation_data:
				if obj and obj.animation_data and obj.animation_data.action:
					action = obj.animation_data.action
					for index, fcurve in enumerate(action.fcurves):
						# Get base property name and index
						data_path = fcurve.data_path
						array_index = fcurve.array_index
						
						# Default label
						label = data_path
						
						# Try to improve naming for common array-type properties
						axis_labels = {
							"location": ["X", "Y", "Z"],
							"scale": ["X", "Y", "Z"],
							"rotation_euler": ["X", "Y", "Z"],
							"rotation_quaternion": ["W", "X", "Y", "Z"],
							"delta_location": ["X", "Y", "Z"],
							"delta_rotation_euler": ["X", "Y", "Z"],
							"delta_scale": ["X", "Y", "Z"]
						}
						
						short_path = data_path.split('.')[-1]
						
						if short_path in axis_labels:
							axis = axis_labels[short_path][array_index]
							label = f"{short_path.replace('_', ' ').title()} {axis}"
						else:
							# Fallback: include array index if applicable
							if fcurve.array_index != -1:
								label = f"{data_path}[{array_index}]"
						
						items.append((str(index), label, ""))
		return items
	
	driver_curve_offset: bpy.props.StringProperty(
		name="Offset",
		default="frame - 10")
	
	
	
	# Easing
	driver_value_t: bpy.props.StringProperty(
		name="Time",
		description='Time value for interpolation',
		default='frame/60')
	driver_ease_type: bpy.props.EnumProperty(
		name='Easing',
		description='Ease type',
		items=[
			('linear', 'Linear', 'No interpolation, passes the input value without change'),
			('smooth', 'Smooth', 'Smoothstep interpolation'),
#			('smoothx', 'Smooth x2', 'Smoothstep interpolation calculated twice for extra-crazy-smooth results'),
			('smoother', 'Smoother', 'Smootherstep interpolation'),
			('sine', 'Sine', 'Sine wave curvature'),
			('quad', 'Quad', 'Quadratic curvature'),
			('cubic', 'Cubic', 'Cubic curvature'),
			('quart', 'Quartic', 'Quartic curvature'),
			('quint', 'Quintic', 'Quinctic curvature'),
			('expo', 'Exponential', 'Exponential curvature'),
			('circ', 'Circular', 'Circular curvature'),
			('back', 'Back (rebound)', 'Overshoots the source and/or target values'),
			('elastic', 'Elastic', 'Springy oscillation from or to source and target values'),
			('bounce', 'Bounce', 'Gravitational bounce from or to source and target values'),
			],
		default='smooth')
	driver_ease_direction: bpy.props.EnumProperty(
		name='Direction',
		description='Ease direction',
		items=[
			('in', 'In', 'Interpolate the start of a time range'),
			('out', 'Out', 'Interpolate the end of a time range'),
			('inout', 'In+Out', 'Interpolate the start and end of a time range'),
			],
		default='inout')
	
	
	# Lerp / Mix (also used for Marker Range)
	driver_value_a: bpy.props.FloatProperty(
		name="Value A",
		description='Value at the start of a mix or marker range',
		default=0.0)
	driver_value_b: bpy.props.FloatProperty(
		name="Value B",
		description='Value at the end of a mix or marker range',
		default=1.0)
	driver_value_c: bpy.props.FloatProperty(
		name="Value C",
		description='Mix between values A and B',
		default=0.5)
	
	
	
	# Marker
	driver_marker_name: bpy.props.StringProperty(
		name="Marker",
		description='Name of the target marker',
		default="")
	driver_marker_end: bpy.props.StringProperty(
		name="Marker",
		description='Name of the target marker',
		default="")
	driver_marker_filter: bpy.props.EnumProperty(
		name='Filter',
		description='Marker filtering options',
		items=[
			('ALL', 'All Markers', 'Use all markers in the scene timeline'),
			('FILTER', 'Filtered', 'Use only markers that contain the specified string'),
			],
		default='ALL')
	driver_marker_string: bpy.props.StringProperty(
		name="Filter String",
		description='String to check marker names against',
		default="marker_")
	driver_marker_relative: bpy.props.EnumProperty(
		name='Value',
		description='Type of marker value',
		items=[
			('STATIC', 'Static Value', 'Marker point within the scene timeline'),
			('RELATIVE', 'Relative Timeline', 'Scene timeline shifted to start at the marker point'),
			],
		default='STATIC')
	driver_marker_seconds: bpy.props.EnumProperty(
		name='Format',
		description='Marker value format',
		items=[
			('FRAMES', 'Frames', 'Use frame integer value'),
			('SECONDS', 'Seconds', 'Use floating point time value'),
			],
		default='FRAMES')
	driver_marker_clamp: bpy.props.EnumProperty(
		name='Clamp',
		description='Type of marker value',
		items=[
			('INF', 'Infinite', 'Float values before and after the range will continue the value ramp'),
			('CLAMP', 'Clamped', 'Clamp value ramp to 0-1 range'),
			],
		default='INF')
	driver_marker_duration: bpy.props.FloatProperty(
		name="Duration",
		default=1.0)
	
	
	# Random
	driver_random_min: bpy.props.FloatProperty(
		name="Minimum",
		default=0.0)
	driver_random_max: bpy.props.FloatProperty(
		name="Maximum",
		default=1.0)
	driver_random_seed: bpy.props.FloatProperty(
		name="Seed",
		default=0.0)
	
	# Wiggle
	driver_wiggle_frequency: bpy.props.FloatProperty(
		name="Frequency",
		default=2.0)
	driver_wiggle_amplitude: bpy.props.FloatProperty(
		name="Amplitude",
		default=1.0)
	driver_wiggle_octaves: bpy.props.FloatProperty(
		name="Octaves",
		default=3.0)
	driver_wiggle_seed: bpy.props.FloatProperty(
		name="Seed",
		default=0.0)
	
	
	
	########## Vertex Location Keyframes ##########
	
	vertex_location_x: bpy.props.BoolProperty(
		name="Location X",
		description="Enable/disable keyframing of the X location channel",
		default=True)
	vertex_location_y: bpy.props.BoolProperty(
		name="Location Y",
		description="Enable/disable keyframing of the Y location channel",
		default=True)
	vertex_location_z: bpy.props.BoolProperty(
		name="Location Z",
		description="Enable/disable keyframing of the Z location channel",
		default=True)
	vertex_location_world_space: bpy.props.BoolProperty(
		name="World Space",
		description="Enable/disable world space vertex locations (when disabled the vertex locations will be relative to the mesh object)",
		default=True)
	vertex_location_shuffle_order: bpy.props.BoolProperty(
		name="Shuffle Order",
		description="Enable/disable randomisation of the order that items are associated with vertices (when disabled the item and vertex groups are sorted by internal ID, typically order of creation)",
		default=False)
	vertex_location_shuffle_timing: bpy.props.BoolProperty(
		name="Shuffle Timing",
		description="Enable/disable randomisation of the sequence order (this maintains the item and vertex order, but randomises the application of time offsets)",
		default=False)
	vertex_location_keyframe_offset: bpy.props.IntProperty(
		name="Frame Offset",
		description="Number of frames each sequential keyframe will be offset by",
		default=1)





###########################################################################
# Addon registration functions
# •Define classes being registered
# •Define keymap array
# •Registration function
# •Unregistration function

classes = (ProductionKitPreferences, ProductionKitSettings,
	ColorPaletteProperty, AddColorOperator, RemoveColorOperator, ReorderColorOperator, CopyColorOperator, EditPaletteOperator, SavePaletteOperator, LoadPaletteOperator, PRODUCTIONKIT_PT_colorPalette,
	PRODUCTIONKIT_OT_SaveProjectVersion,
	Production_Kit_Update_Images, Production_Kit_Switch_Extension_Inputs, Production_Kit_Replace_Extensions, PRODUCTIONKIT_PT_update_images_ui,
	PRODUCTIONKIT_OT_set_viewport_shading)

keymaps = []



def register():
	# Register classes
	for cls in classes:
		bpy.utils.register_class(cls)
	
	# Add extension settings reference
	bpy.types.Scene.production_kit_settings = bpy.props.PointerProperty(type=ProductionKitSettings)
	
	
	########## Project Version ##########
	# Add project version to file menu
	bpy.types.TOPBAR_MT_file.append(TOPBAR_MT_file_save_version)
	
	
	########## Update Images ##########
	# Add image refresh button to the image menu
	bpy.types.IMAGE_MT_image.append(production_kit_update_images_menu_item)
	
	
	########## Audio Waveforms FFmpeg Check ##########
	bpy.context.preferences.addons[__package__].preferences.check_ffmpeg_location()
	
	
	########## Register Components ##########
	audio_waveforms.register()
	cycle_transforms.register()
	driver_functions.register()
	transfer_to_scene.register()
	vertex_locations.register()
	
	
	########## Colour Palette ##########
	# Add local scene settings
	bpy.types.Scene.palette_local = bpy.props.CollectionProperty(type=ColorPaletteProperty)
	
	
	########## Viewport Shading ##########
	bpy.types.VIEW3D_MT_view.append(production_kit_viewport_shading_menu_items)
	
	
	# Add keymaps for project versioning and viewport shading
	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon
	if kc:
		
		########## Project Version ##########
		
		# Linux/Windows Increment/Increment Minor
		km = wm.keyconfigs.addon.keymaps.new(name='Window')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_SaveProjectVersion.bl_idname, 'S', 'PRESS', ctrl=True, alt=True, shift=True)
		kmi.properties.increment_major = False
		keymaps.append((km, kmi))
		
		## MacOS Increment/Increment Minor
		km = wm.keyconfigs.addon.keymaps.new(name='Window')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_SaveProjectVersion.bl_idname, 'S', 'PRESS', oskey=True, alt=True, shift=True)
		kmi.properties.increment_major = False
		keymaps.append((km, kmi))
		
		## MacOS Increment Major
		km = wm.keyconfigs.addon.keymaps.new(name='Window')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_SaveProjectVersion.bl_idname, 'S', 'PRESS', oskey=True, ctrl=True, alt=True, shift=True)
		kmi.properties.increment_major = True
		keymaps.append((km, kmi))
		
		########## Viewport Shading ##########
		
		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_1', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F1', 'PRESS', alt=True)
		kmi.properties.rendertype = 'WIREFRAME'
		keymaps.append((km, kmi))
		
		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_2', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F2', 'PRESS', alt=True)
		kmi.properties.rendertype = 'SOLID'
		keymaps.append((km, kmi))
		
		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_3', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F3', 'PRESS', alt=True)
		kmi.properties.rendertype = 'MATERIAL'
		keymaps.append((km, kmi))
		
		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_0', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F4', 'PRESS', alt=True)
		kmi.properties.rendertype = 'RENDERED'
		keymaps.append((km, kmi))



def unregister():
	# Remove keymaps
	for km, kmi in keymaps:
		km.keymap_items.remove(kmi)
	keymaps.clear()
	
	
	########## Project Version ##########
	bpy.types.TOPBAR_MT_file.remove(TOPBAR_MT_file_save_version)
	
	
	########## Update Images ##########
	bpy.types.IMAGE_MT_image.remove(production_kit_update_images_menu_item)
	
	
	########## Colour Palette ##########
	# Remove local scene settings
	del bpy.types.Scene.palette_local
	
	
	########## Unregister Components ##########
	audio_waveforms.unregister()
	cycle_transforms.unregister()
	driver_functions.unregister()
	transfer_to_scene.unregister()
	vertex_locations.unregister()
	
	
	########## Viewport Shading ##########
	bpy.types.VIEW3D_MT_view.remove(production_kit_viewport_shading_menu_items)
	
	
	# Remove extension settings reference
	del bpy.types.Scene.production_kit_settings
	
	# Deregister classes
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)



if __package__ == "__main__":
	register()