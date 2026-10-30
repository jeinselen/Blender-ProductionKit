import bpy
from bpy.app.handlers import persistent


###########################################################################
# Driver Pickwhip
#
# Two complementary workflows are exposed in every RNA property context menu:
#
# 1. Blender's native driver eyedropper for properties that are already visible.
# 2. A non-modal, two-stage workflow that stores a destination, releases the UI
#    for normal navigation, then connects the next source property chosen from
#    its context menu.


_TRANSFORM_TYPES = {
	"location": ("LOC_X", "LOC_Y", "LOC_Z"),
	"scale": ("SCALE_X", "SCALE_Y", "SCALE_Z"),
}


def _active_property(context):
	"""Return an ID-backed property tuple from the button under the cursor."""
	prop = getattr(context, "property", None)
	if not prop or len(prop) != 3:
		return None
	id_block, data_path, array_index = prop
	if not isinstance(id_block, bpy.types.ID) or not data_path:
		return None
	return id_block, data_path, array_index


def _library_path(id_block):
	library = getattr(id_block, "library", None)
	return library.filepath if library else ""


def _id_label(id_block):
	return getattr(id_block, "name_full", None) or getattr(id_block, "name", "<unnamed>")


def _property_label(id_block, data_path, array_index):
	index = f"[{array_index}]" if array_index >= 0 else ""
	return f"{_id_label(id_block)} › {data_path}{index}"


def _state(context):
	return context.window_manager.production_kit_driver_pickwhip


def _clear_state(state):
	state.armed = False
	state.destination_id_type = ""
	state.destination_id_name = ""
	state.destination_library = ""
	state.destination_session_uid = ""
	state.destination_path = ""
	state.destination_index = -1
	state.destination_label = ""


def _iter_ids():
	"""Iterate ID datablocks without depending on Blender 5.2's bpy.data.all_ids."""
	seen = set()
	for rna_prop in bpy.data.bl_rna.properties:
		if getattr(rna_prop, "type", None) != 'COLLECTION':
			continue
		collection = getattr(bpy.data, rna_prop.identifier, None)
		if collection is None:
			continue
		try:
			items = iter(collection)
		except TypeError:
			continue
		for item in items:
			if not isinstance(item, bpy.types.ID):
				continue
			pointer = item.as_pointer()
			if pointer in seen:
				continue
			seen.add(pointer)
			yield item


def _resolve_destination(state):
	"""Resolve the stored ID after navigation, rename, undo, or UI changes."""
	uid = state.destination_session_uid
	if uid:
		for id_block in _iter_ids():
			if str(getattr(id_block, "session_uid", "")) == uid:
				return id_block

	# Name/type/library fallback is useful after undo recreates an ID.
	for id_block in _iter_ids():
		if getattr(id_block, "id_type", "") != state.destination_id_type:
			continue
		if _id_label(id_block) != state.destination_id_name:
			continue
		if _library_path(id_block) == state.destination_library:
			return id_block
	return None


def _path_resolves(id_block, data_path):
	try:
		id_block.path_resolve(data_path)
		return True
	except (AttributeError, ValueError):
		return False


def _existing_driver(id_block, data_path, array_index):
	animation_data = getattr(id_block, "animation_data", None)
	if not animation_data:
		return None
	for fcurve in animation_data.drivers:
		if fcurve.data_path != data_path:
			continue
		if array_index < 0 or fcurve.array_index == array_index:
			return fcurve
	return None


def _resolved_parent_and_property(id_block, data_path):
	"""Resolve the RNA struct that owns the last named component of a path."""
	if "." in data_path:
		parent_path, prop_name = data_path.rsplit(".", 1)
		try:
			parent = id_block.path_resolve(parent_path)
		except (AttributeError, ValueError):
			return None, ""
	else:
		parent = id_block
		prop_name = data_path

	# Custom-property paths end in ["name"] and are not RNA identifiers.
	if prop_name.startswith("["):
		return parent, ""
	return parent, prop_name


def _property_unit(id_block, data_path):
	parent, prop_name = _resolved_parent_and_property(id_block, data_path)
	if parent is None or not prop_name or not hasattr(parent, "bl_rna"):
		return 'NONE'
	prop = parent.bl_rna.properties.get(prop_name)
	return getattr(prop, "unit", 'NONE') if prop else 'NONE'


def _driver_expression(destination_id, destination_path, source_id, source_path):
	destination_unit = _property_unit(destination_id, destination_path)
	source_unit = _property_unit(source_id, source_path)
	if destination_unit == 'ROTATION' and source_unit != 'ROTATION':
		return "radians(source)"
	if source_unit == 'ROTATION' and destination_unit != 'ROTATION':
		return "degrees(source)"
	return "source"


def _same_rna_owner(destination_id, destination_path, source_id, source_path):
	if destination_id != source_id:
		return False
	destination_parent, _ = _resolved_parent_and_property(destination_id, destination_path)
	source_parent, _ = _resolved_parent_and_property(source_id, source_path)
	return destination_parent == source_parent


def _transform_source(source_id, source_path, source_index):
	"""Return (owner, property name, optional bone name) for native-style transforms."""
	parent, prop_name = _resolved_parent_and_property(source_id, source_path)
	if not isinstance(parent, (bpy.types.Object, bpy.types.PoseBone)):
		return None
	if prop_name not in {"location", "scale"} and not prop_name.startswith("rotation_"):
		return None
	if source_index < 0:
		source_index = 0
	bone_name = parent.name if isinstance(parent, bpy.types.PoseBone) else ""
	return parent, prop_name, bone_name, source_index


def _configure_variable(driver, destination_id, destination_path, source_id, source_path, source_index):
	for variable in list(driver.variables):
		driver.variables.remove(variable)

	variable = driver.variables.new()
	variable.name = "source"
	target = variable.targets[0]
	transform = _transform_source(source_id, source_path, source_index)

	# Match Blender's native picker: use a Transform Channel for object/bone
	# transforms, except on the same RNA owner where it can create a dependency
	# cycle. Other values use a Single Property variable.
	if transform and not _same_rna_owner(destination_id, destination_path, source_id, source_path):
		_parent, prop_name, bone_name, index = transform
		variable.type = 'TRANSFORMS'
		target.id = source_id
		if bone_name:
			target.bone_target = bone_name
		if prop_name in _TRANSFORM_TYPES:
			target.transform_type = _TRANSFORM_TYPES[prop_name][min(index, 2)]
		else:
			# This deliberately mirrors Blender's native quaternion/axis-angle
			# fallback: indices other than Y/Z map to rotation X.
			target.transform_type = ("ROT_X", "ROT_Y", "ROT_Z")[min(index, 2)]
	else:
		variable.type = 'SINGLE_PROP'
		target.id_type = source_id.id_type
		target.id = source_id
		indexed_path = f"{source_path}[{source_index}]"
		target.data_path = indexed_path if source_index >= 0 and _path_resolves(source_id, indexed_path) else source_path


def _remove_created_drivers(id_block, fcurves):
	for fcurve in fcurves:
		try:
			id_block.driver_remove(fcurve.data_path, fcurve.array_index)
		except (ReferenceError, RuntimeError, TypeError):
			pass


###########################################################################
# State and operators


class PRODUCTIONKIT_PG_driver_pickwhip(bpy.types.PropertyGroup):
	armed: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
	destination_id_type: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
	destination_id_name: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
	destination_library: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
	destination_session_uid: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
	destination_path: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
	destination_index: bpy.props.IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'})
	destination_label: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})


class PRODUCTIONKIT_OT_arm_driver_destination(bpy.types.Operator):
	"""Remember this property as the driven destination, then allow normal navigation before choosing its source"""
	bl_idname = "productionkit.arm_driver_destination"
	bl_label = "Arm as Driver Destination"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context):
		return _active_property(context) is not None

	def execute(self, context):
		active = _active_property(context)
		if not active:
			self.report({'ERROR'}, "No ID-backed property under the cursor")
			return {'CANCELLED'}

		id_block, data_path, array_index = active
		if not _path_resolves(id_block, data_path):
			self.report({'ERROR'}, "The destination property has no resolvable RNA path")
			return {'CANCELLED'}
		if _existing_driver(id_block, data_path, array_index):
			self.report({'ERROR'}, "The destination property already has a driver")
			return {'CANCELLED'}

		state = _state(context)
		state.armed = True
		state.destination_id_type = id_block.id_type
		state.destination_id_name = _id_label(id_block)
		state.destination_library = _library_path(id_block)
		state.destination_session_uid = str(getattr(id_block, "session_uid", ""))
		state.destination_path = data_path
		state.destination_index = array_index
		state.destination_label = _property_label(id_block, data_path, array_index)
		self.report({'INFO'}, f"Driver destination armed: {state.destination_label}")
		return {'FINISHED'}


class PRODUCTIONKIT_OT_connect_driver_source(bpy.types.Operator):
	"""Use this property as the source for the armed driver destination"""
	bl_idname = "productionkit.connect_driver_source"
	bl_label = "Connect to Armed Driver Destination"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		state = getattr(context.window_manager, "production_kit_driver_pickwhip", None)
		return bool(state and state.armed and _active_property(context))

	def execute(self, context):
		state = _state(context)
		source = _active_property(context)
		if not state.armed or not source:
			self.report({'ERROR'}, "Arm a destination, then right-click an ID-backed source property")
			return {'CANCELLED'}

		destination_id = _resolve_destination(state)
		if destination_id is None:
			self.report({'ERROR'}, "The armed destination datablock no longer exists")
			_clear_state(state)
			return {'CANCELLED'}

		destination_path = state.destination_path
		destination_index = state.destination_index
		source_id, source_path, source_index = source

		if not _path_resolves(destination_id, destination_path):
			self.report({'ERROR'}, "The armed destination property no longer exists")
			_clear_state(state)
			return {'CANCELLED'}
		if not _path_resolves(source_id, source_path):
			self.report({'ERROR'}, "The source property has no resolvable RNA path")
			return {'CANCELLED'}
		if destination_id == source_id and destination_path == source_path and destination_index == source_index:
			self.report({'ERROR'}, "A property cannot drive itself")
			return {'CANCELLED'}
		if _existing_driver(destination_id, destination_path, destination_index):
			self.report({'ERROR'}, "The armed destination already has a driver")
			return {'CANCELLED'}

		created = []
		try:
			result = destination_id.driver_add(destination_path, destination_index)
			created = result if isinstance(result, list) else [result]
			for fcurve in created:
				driver = fcurve.driver
				driver.type = 'SCRIPTED'
				driver.expression = _driver_expression(
					destination_id, destination_path, source_id, source_path)
				_configure_variable(
					driver,
					destination_id,
					destination_path,
					source_id,
					source_path,
					source_index,
				)
		except Exception as exc:
			_remove_created_drivers(destination_id, created)
			self.report({'ERROR'}, f"Could not create driver: {exc}")
			return {'CANCELLED'}

		destination_label = state.destination_label
		source_label = _property_label(source_id, source_path, source_index)
		_clear_state(state)
		destination_id.update_tag()
		context.view_layer.update()
		self.report({'INFO'}, f"Connected {source_label} → {destination_label}")
		return {'FINISHED'}


class PRODUCTIONKIT_OT_clear_driver_destination(bpy.types.Operator):
	"""Clear the currently armed driver destination"""
	bl_idname = "productionkit.clear_driver_destination"
	bl_label = "Clear Armed Driver Destination"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context):
		state = getattr(context.window_manager, "production_kit_driver_pickwhip", None)
		return bool(state and state.armed)

	def execute(self, context):
		_clear_state(_state(context))
		self.report({'INFO'}, "Armed driver destination cleared")
		return {'FINISHED'}


###########################################################################
# UI and registration


def driver_pickwhip_context_menu(self, context):
	active = _active_property(context)
	if not active:
		return

	layout = self.layout
	layout.separator()

	# Native, blocking picker for source properties that are already visible.
	row = layout.row()
	row.operator_context = 'INVOKE_DEFAULT'
	operator = row.operator(
		"ui.eyedropper_driver",
		text="Pick Driver Source (Visible)",
		icon='EYEDROPPER',
	)
	operator.mapping_type = 'DIRECT'

	state = _state(context)
	if state.armed:
		layout.label(text=f"Armed: {state.destination_label}", icon='DRIVER')
		layout.operator(
			PRODUCTIONKIT_OT_connect_driver_source.bl_idname,
			text="Connect Armed Destination from This Value",
			icon='LINKED',
		)
		layout.operator(
			PRODUCTIONKIT_OT_arm_driver_destination.bl_idname,
			text="Re-arm Destination Here",
			icon='DECORATE_DRIVER',
		)
		layout.operator(
			PRODUCTIONKIT_OT_clear_driver_destination.bl_idname,
			text="Clear Armed Destination",
			icon='X',
		)
	else:
		layout.operator(
			PRODUCTIONKIT_OT_arm_driver_destination.bl_idname,
			text="Arm as Driver Destination",
			icon='DECORATE_DRIVER',
		)


@persistent
def _clear_pickwhip_on_load(_dummy):
	for window_manager in bpy.data.window_managers:
		state = getattr(window_manager, "production_kit_driver_pickwhip", None)
		if state:
			_clear_state(state)


classes = (
	PRODUCTIONKIT_PG_driver_pickwhip,
	PRODUCTIONKIT_OT_arm_driver_destination,
	PRODUCTIONKIT_OT_connect_driver_source,
	PRODUCTIONKIT_OT_clear_driver_destination,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.WindowManager.production_kit_driver_pickwhip = bpy.props.PointerProperty(
		type=PRODUCTIONKIT_PG_driver_pickwhip)
	bpy.types.UI_MT_button_context_menu.append(driver_pickwhip_context_menu)
	bpy.app.handlers.load_post.append(_clear_pickwhip_on_load)


def unregister():
	if _clear_pickwhip_on_load in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(_clear_pickwhip_on_load)
	bpy.types.UI_MT_button_context_menu.remove(driver_pickwhip_context_menu)
	del bpy.types.WindowManager.production_kit_driver_pickwhip
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

