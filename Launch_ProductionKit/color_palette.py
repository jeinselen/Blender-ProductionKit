import bpy
import os

#prefs = bpy.context.preferences.addons[__package__].preferences
#settings = bpy.context.scene.render_kit_settings

###########################################################################
# Property group definition

# Define the property group for color palette
class ColorPaletteProperty(bpy.types.PropertyGroup):
	name: bpy.props.StringProperty(
		name='Name',
		default='Color'
	)
	color: bpy.props.FloatVectorProperty(
		name="Color",
		subtype='COLOR',
		size=4,
		default=(1.0, 1.0, 1.0, 1.0)
	)

###########################################################################
# Palette management operators

class AddColorOperator(bpy.types.Operator):
	bl_idname = "ed.palette_add_color"
	bl_label = "Add Color"
	
	def execute(self, context):
		palette = context.scene.palette_local.add()
		palette.name = f"Color {len(context.scene.palette_local)}"
		# This operator may be called when no palette exists yet, so it's important to enter edit mode to allow saving
		bpy.context.scene.production_kit_settings.palette_edit = True
		return {'FINISHED'}

class RemoveColorOperator(bpy.types.Operator):
	bl_idname = "ed.palette_remove_color"
	bl_label = "Remove Color Palette"
	
	palette_index: bpy.props.IntProperty()
	
	def execute(self, context):
		context.scene.palette_local.remove(self.palette_index)
		return {'FINISHED'}

class ReorderColorOperator(bpy.types.Operator):
	bl_idname = "ed.palette_reorder_color"
	bl_label = "Reorder Color Palette"
	
	palette_index: bpy.props.IntProperty()
	new_index: bpy.props.IntProperty()
	
	def execute(self, context):
		context.scene.palette_local.move(self.palette_index, self.new_index)
		return {'FINISHED'}

class CopyColorOperator(bpy.types.Operator):
	bl_idname = "ed.palette_copy_color"
	bl_label = "Copy Color"
	
	palette_index: bpy.props.IntProperty()
	
	def execute(self, context):
		palette = context.scene.palette_local[self.palette_index]
		color_str = '[' + ", ".join([str(value) for value in palette.color]) + ']'
		context.window_manager.clipboard = color_str
		return {'FINISHED'}

###########################################################################
# Palette editing operators

# Edit Palette
class EditPaletteOperator(bpy.types.Operator):
	bl_idname = "ed.palette_edit"
	bl_label = "Edit"
	
	def execute(self, context):
		load_palette_from_file(context.preferences.addons[__package__].preferences.palette_file_location)
		bpy.context.scene.production_kit_settings.palette_edit = True
		return {'FINISHED'}

# Save Palette
class SavePaletteOperator(bpy.types.Operator):
	bl_idname = "ed.palette_save"
	bl_label = "Save"
	
	def execute(self, context):
		save_palette_to_file(context.preferences.addons[__package__].preferences.palette_file_location)
		bpy.context.scene.production_kit_settings.palette_edit = False
		return {'FINISHED'}

# Load Palette Operator
class LoadPaletteOperator(bpy.types.Operator):
	bl_idname = "ed.palette_load"
	bl_label = "Load Palette"
	
	def execute(self, context):
		load_palette_from_file(context.preferences.addons[__package__].preferences.palette_file_location)
		bpy.context.scene.production_kit_settings.palette_edit = False
		return {'FINISHED'}

###########################################################################
# Palette open/save functions

def save_palette_to_file(filepath):
	try:
		filepath = os.path.join(filepath, bpy.context.preferences.addons[__package__].preferences.palette_file_name)
		filepath = bpy.path.abspath(filepath)
			
		with open(filepath, 'w') as file:
			for palette in bpy.context.scene.palette_local:
				color = ",".join([str(value) for value in palette.color])
				file.write(f"{palette.name}={color}\n")
	except Exception as exc:
		print(str(exc) + " | Error in Production Kit save palette file function")

def load_palette_from_file(filepath):
	try:
		filepath = os.path.join(filepath, bpy.context.preferences.addons[__package__].preferences.palette_file_name)
		filepath = bpy.path.abspath(filepath)
		
		bpy.context.scene.palette_local.clear()
		
		with open(filepath, 'r') as file:
			lines = file.readlines()
			for line in lines:
				name, color_str = line.strip().split('=')
				color_values = [float(value) for value in color_str.split(',')]
				palette = bpy.context.scene.palette_local.add()
				palette.name = name
				palette.color = color_values
	except Exception as exc:
		print(str(exc) + " | Error in Production Kit load palette file function")



###########################################################################
# UI rendering class

class PRODUCTIONKIT_PT_colorPalette(bpy.types.Panel):
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Launch"
	bl_order = 4
	bl_options = {'DEFAULT_CLOSED'}
	bl_label = "Color Palette"
	bl_idname = "PRODUCTIONKIT_PT_colorPalette"
	
	@classmethod
	def poll(cls, context):
		return True #len(bpy.data.filepath) > 0
	
	def draw_header(self, context):
		try:
			layout = self.layout
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit palette panel header")
			
	def draw(self, context):
		try:
			layout = self.layout
			layout.use_property_decorate = False # No animation
			
			# If project file isn't saved yet
			if not bpy.data.filepath:
				box = layout.box()
				col = box.column(align=True)
				col.label(text='Project must be saved first')
				col.label(text='to create or load color palette')
			else:
				# If no local palette entries exist yet
				if len(context.scene.palette_local) < 1:
					# Check for local file
					filepath = os.path.join(context.preferences.addons[__package__].preferences.palette_file_location, context.preferences.addons[__package__].preferences.palette_file_name)
					filepath = bpy.path.abspath(filepath)
					if os.path.isfile(filepath):
						layout.operator("ed.palette_load", text="Load Palette", icon='FILE') # FILE FILE_BLANK FILE_CACHE FILE_REFRESH
					else:
						layout.operator("ed.palette_add_color", text='Create Palette', icon='ADD')
				else:
					# If in edit mode
					if bpy.context.scene.production_kit_settings.palette_edit:
						edit_grid = layout.grid_flow(row_major=False, columns=0, even_columns=True, even_rows=True, align=False)
						for index, color in enumerate(context.scene.palette_local):
							row = edit_grid.row(align=False)
							row.prop(color, "color", text='')
							row.prop(color, "name", text='')
							buttons = row.row(align=True)
							move_up = buttons.operator("ed.palette_reorder_color", text='', icon='TRIA_UP')
							move_up.palette_index = index
							move_up.new_index = index - 1
							move_down = buttons.operator("ed.palette_reorder_color", text='', icon='TRIA_DOWN')
							move_down.palette_index = index
							move_down.new_index = index + 1
							buttons.operator("ed.palette_remove_color", text='', icon='X').palette_index = index
						layout.operator("ed.palette_add_color", icon='ADD') # ADD PLUS PRESET_NEW
						row = layout.row()
						row.operator("ed.palette_load", text='Cancel', icon='CANCEL')
						row.operator("ed.palette_save", icon='CURRENT_FILE') # CURRENT_FILE
					# Standard display
					else:
						display_grid = layout.grid_flow(row_major=False, columns=0, even_columns=True, even_rows=True, align=False)
						for index, color in enumerate(context.scene.palette_local):
							row = display_grid.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
							row.prop(color, "color", text='')
							row.operator("ed.palette_copy_color", text=color.name, icon='COPYDOWN').palette_index = index
						row = layout.row()
						row.operator("ed.palette_edit", icon='PREFERENCES') # PREFERENCES
				
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit palette panel")
