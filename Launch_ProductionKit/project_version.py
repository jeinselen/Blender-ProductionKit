import bpy
import datetime
import os
from re import findall, search, split, M as multiline

###########################################################################
# Save new file version

class PRODUCTIONKIT_OT_SaveProjectVersion(bpy.types.Operator):
	bl_idname = "wm.saveprojectversion"
	bl_label = "Save Project Version"
	bl_description = "Save a versioned project file in the specified directory"
	bl_space_type = "TOPBAR"
	bl_region_type = 'UI'
	
	increment_major: bpy.props.BoolProperty(default=False)
	
	def invoke(self, context, event):
		prefs = context.preferences.addons[__package__].preferences
		
		# Define project names
		project_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
		
		# Get preferences
		version_path = bpy.path.abspath(prefs.version_path)
		version_type = prefs.version_type
		if (prefs.version_auto):
			alphanum = search('(\d+[A-Za-z]{1})$', project_name)
			if alphanum is not None:
				version_type = 'ALPHANUM'
		version_separator = prefs.version_separator
		if version_type == 'ALPHANUM':
			version_length = format(prefs.version_length - 1, '02')
		else:
			version_length = format(prefs.version_length, '02')
		version_compress = prefs.version_compress
		version_keepbackup = prefs.version_keepbackup
		
		# Define project paths
		project_path = os.path.dirname(bpy.data.filepath)
		
		# If project hasn't been saved yet, open a save dialogue
		if len(project_path) < 1:
			# Open save dialogue
			bpy.ops.wm.save_mainfile('INVOKE_AREA')
			return {'FINISHED'}
		
		# If empty or single character, use a folder with the same name as the project file
		if len(version_path) <= 1:
			# Replace one or fewer characters with the project path
			version_path = os.path.join(os.path.dirname(bpy.data.filepath), project_name)
		
		# Convert relative paths into absolute paths for Python compatibility
		project_path = bpy.path.abspath(project_path)
		version_path = bpy.path.abspath(version_path)
		
		# Create version directory if it doesn't exist yet
		if not os.path.exists(version_path):
			os.makedirs(version_path)
		
		# Generate file name with numerical identifier
		if version_type == 'NUM': # Generate dynamic serial number
			# Finds all project files that start with project_name in the selected directory
			files = [f for f in os.listdir(version_path) if f.startswith(project_name) and f.lower().endswith(".blend")]
			
			# Searches the file collection and returns the next highest number as a formated string
			def save_number_from_files(files):
				highest = -1
				if files:
					for f in files:
						# find filenames that end with digits
						suffix = findall(r'\d+$', os.path.splitext(f)[0].split(project_name)[-1], multiline)
						if suffix:
							if int(suffix[-1]) > highest:
								highest = int(suffix[-1])
				return format(highest + 1, version_length)
			
			# Create string with serial number
			version_name = project_name + version_separator + save_number_from_files(files)
		
		# Generate file name with date and time
		elif version_type == 'TIME':
			# Create string with date and time
			version_name = project_name + version_separator + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
		
		# If set to alphanumeric, separate version elements from project name, increment, recombine
		elif version_type == 'ALPHANUM':
			project_name_parts = split(r'([0-9]{1,})([a-z]{1})$', project_name)
			# If project is already versioned, increment
			if len(project_name_parts) > 3:
				# Increment values (major: "001x" to "002a", minor: "001a" to "001b")
				if self.increment_major:
					project_num = format(int(project_name_parts[1]) + 1, version_length)
					project_chr = "a"
				else:
#					project_num = project_name_parts[1] # This preserve shorter/longer serial number padding if already present
					project_num = format(int(project_name_parts[1]), version_length)
					project_chr = str(chr(ord(project_name_parts[2]) + 1))
				version_name = project_name_parts[0] + project_num + project_chr
			# If project is not yet versioned, create new version
			else:
				project_num = format(1, version_length)
				project_chr = "a"
				version_name = project_name + version_separator + project_num + project_chr
		
		
		
		# Save version
		if version_type != 'ALPHANUM':
			# Save copy of current project with new name in the archive location
			version_file = os.path.join(version_path, version_name) + '.blend'
			bpy.ops.wm.save_as_mainfile(filepath=version_file, compress=version_compress, relative_remap=True, copy=True)
		else:
			# Save current project with new serial number in the current location
			project_file = os.path.join(project_path, version_name) + '.blend'
			bpy.ops.wm.save_as_mainfile(filepath=project_file, compress=version_compress)
			
			# Move previous project file to the archive location
			old_path = os.path.join(project_path, project_name)
			new_path = os.path.join(version_path, project_name)
			os.rename(old_path + '.blend', new_path + '.blend')
			
			# Move or delete backup file
			if os.path.isfile(old_path + '.blend1'):
				if version_keepbackup:
					os.remove(old_path + '.blend1')
				else:
					os.rename(old_path + '.blend1', new_path + '.blend1')
			
			# Also move autosave render folder (if it exists and uses the same name as the project)
			if os.path.exists(old_path):
				os.rename(old_path, new_path)
		
		
		
		# Build display path to display success feedback
		display_path = prefs.version_path
		if len(display_path) <= 1:
			display_path = project_name
		display_path = os.path.join(display_path, version_name + '.blend')
		
		# Provide success feedback
		self.report ({'INFO'}, "Version saved successfully: " + display_path)
		if prefs.version_popup:
			def draw(self, context):
				self.layout.label(text=display_path)
			bpy.context.window_manager.popup_menu(draw, title="Version Saved Successfully", icon='FOLDER_REDIRECT') # Alt: INFO
		
		# Done
		return {'FINISHED'}



###########################################################################
# Menu UI
		
def TOPBAR_MT_file_save_version(self, context):
	bl_idname = 'TOPBAR_MT_file_save_version'
	self.layout.separator()
	if context.preferences.addons[__package__].preferences.version_type == 'ALPHANUM':
		minor = self.layout.operator(PRODUCTIONKIT_OT_SaveProjectVersion.bl_idname, text = "Save Minor Version", icon = "FOLDER_REDIRECT")
		minor.increment_major = False
		major = self.layout.operator(PRODUCTIONKIT_OT_SaveProjectVersion.bl_idname, text = "Save Major Version", icon = "FOLDER_REDIRECT")
		major.increment_major = True
	else:
		self.layout.operator(PRODUCTIONKIT_OT_SaveProjectVersion.bl_idname, text = "Save Version", icon = "FOLDER_REDIRECT")
	# FILE_NEW FILE_TICK FILE_BLEND FOLDER_REDIRECT
