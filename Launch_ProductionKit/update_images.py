import bpy

###########################################################################
# Update images

class Production_Kit_Update_Images(bpy.types.Operator):
	bl_idname = "productionkit.updateimages"
	bl_label = "Update All Images"
	bl_icon = "RENDERLAYERS"
	bl_description = "Process all images, updating colour space and alpha channel settings based on name patterns, and reloading any images that don't have unsaved changes in Blender"
	bl_options = {'REGISTER', 'UNDO'}
	
	reload: bpy.props.BoolProperty()
	format: bpy.props.BoolProperty()
	
	def execute(self, context):
		prefs = context.preferences.addons[__package__].preferences
		
		for image in bpy.data.images:
			# Reload all image files
			if self.reload:
				# Prevent reloading of files that have unsaved changes in Blender
				if not image.is_dirty:
					image.reload()
			
			# Format all image files
			if self.format:
				# Update file settings based on file name matches
				imageName = image.name.lower()
				if prefs.filter1_name.lower() in imageName:
					image.colorspace_settings.name = prefs.filter1_colorspace
					image.alpha_mode = prefs.filter1_alphamode
				elif prefs.filter2_name.lower() in imageName:
					image.colorspace_settings.name = prefs.filter2_colorspace
					image.alpha_mode = prefs.filter2_alphamode
				elif prefs.filter3_name.lower() in imageName:
					image.colorspace_settings.name = prefs.filter3_colorspace
					image.alpha_mode = prefs.filter3_alphamode
				elif prefs.filter4_name.lower() in imageName:
					image.colorspace_settings.name = prefs.filter4_colorspace
					image.alpha_mode = prefs.filter4_alphamode
				elif prefs.filter5_name.lower() in imageName:
					image.colorspace_settings.name = prefs.filter5_colorspace
					image.alpha_mode = prefs.filter5_alphamode
		return {'FINISHED'}

###########################################################################
# Replace images (file extension swap)

class Production_Kit_Switch_Extension_Inputs(bpy.types.Operator):
	bl_idname = "productionkit.switchextension"
	bl_label = "Switch File Extension Settings"
	bl_icon = "FILE_REFRESH"
	bl_description = "Process all images, updating colour space and alpha channel settings based on name patterns, and reloading any images that don't have unsaved changes in Blender"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		settings = context.scene.production_kit_settings
		
		source = settings.file_extension_source
		target = settings.file_extension_target
		settings.file_extension_source = target
		settings.file_extension_target = source
		return {'FINISHED'}

class Production_Kit_Replace_Extensions(bpy.types.Operator):
	bl_idname = "productionkit.replaceextension"
	bl_label = "Replace All Image Extensions"
	bl_icon = "FILE_REFRESH"
	bl_description = "Replace all images that match the source file extension (left) with files using the target file extension (right), assumes that files already exist in the file system"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		settings = context.scene.production_kit_settings
		
		source = settings.file_extension_source
		target = settings.file_extension_target
		
		for image in bpy.data.images:
			# Prevent replacing files that have unsaved changes in Blender
			if not image.is_dirty:
				image.filepath = image.filepath.replace(source, target)
				image.name = image.name.replace(source, target)
#				image.reload()
		settings.file_extension_source = target
		settings.file_extension_target = source
		return {'FINISHED'}



###########################################################################
# Display in Node panel

class PRODUCTIONKIT_PT_update_images_ui(bpy.types.Panel):
	bl_space_type = 'NODE_EDITOR'
	bl_region_type = 'UI'
	bl_category = "Node"
	bl_label = "Update Images"
	
	def draw(self, context):
		prefs = context.preferences.addons[__package__].preferences
		settings = context.scene.production_kit_settings
		
		layout = self.layout
		layout.use_property_decorate = False  # No animation
		layout.use_property_split = True
		
		# Update all images
		if prefs.enable_file_reload and prefs.enable_file_format:
			update_text = 'Update All Images'
		elif prefs.enable_file_reload:
			update_text = 'Reload All Images'
		elif prefs.enable_file_format:
			update_text = 'Format All Images'
		if prefs.enable_file_reload or prefs.enable_file_format:
			ops = layout.operator(Production_Kit_Update_Images.bl_idname, text=update_text, icon='RENDERLAYERS')
			ops.reload = prefs.enable_file_reload
			ops.format = prefs.enable_file_format
		
		# Display source and target file extensions
		row = layout.row(align=True)
#		grid = row.grid_flow(columns=3, align=True)
		row.prop(settings, 'file_extension_source', text='')
		row.operator(Production_Kit_Switch_Extension_Inputs.bl_idname, text='', icon='FILE_REFRESH')
		row.prop(settings, 'file_extension_target', text='')
		row.operator(Production_Kit_Replace_Extensions.bl_idname, text='Replace')

###########################################################################
# Display in Image menu

def production_kit_update_images_menu_item(self, context):
	self.layout.separator()
	self.layout.operator(Production_Kit_Update_Images.bl_idname)
