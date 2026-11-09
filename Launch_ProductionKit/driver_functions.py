import bpy
import ast
import math
from bpy.app.handlers import persistent
from bpy_extras import anim_utils
from colorsys import hsv_to_rgb
from mathutils import noise

from . import utility_panel

########## Marker snapshot cache; the first driver of a frame builds the snapshot, every other driver reuses it until the frame changes again

_marker_snapshot_cache = {}   # scene.as_pointer() -> (frame, snapshot)

class _MarkerSnapshot:
	__slots__ = ("markers", "active_frame", "active_name", "frame_by_name")
	def __init__(self, scene):
		frame_current = scene.frame_current
		# Single RNA pass: capture (frame, name) pairs, the active marker, and a name -> frame lookup, all in one go
		# Active marker = nearest at or before the current frame; ties resolve to the first in collection order (strict >), matching the original per-driver loop
		# frame_by_name keeps the first occurrence of each name, matching the RNA collection's .get(name) / .find(name) (first match wins)
		raw = []
		self.active_frame = -100000
		self.active_name = None
		self.frame_by_name = {}
		for m in scene.timeline_markers:
			f = m.frame
			n = m.name
			raw.append((f, n))
			if f <= frame_current and f > self.active_frame:
				self.active_frame = f
				self.active_name = n
			if n not in self.frame_by_name:
				self.frame_by_name[n] = f
		# Sorted by frame for the prev/next/range/match scans (lets them break early)
		self.markers = sorted(raw, key=lambda fm: fm[0])

def _marker_snapshot(scene):
	key = scene.as_pointer()
	frame = scene.frame_current
	entry = _marker_snapshot_cache.get(key)
	if entry is not None and entry[0] == frame:
		return entry[1]
	snapshot = _MarkerSnapshot(scene)
	_marker_snapshot_cache[key] = (frame, snapshot)
	return snapshot

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

# EXPO
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

# OVER
c1 = 1.70158
c2 = c1 * 1.525
c3 = c1 + 1
def ease_in_over(t): return c3 * t * t * t - c1 * t * t
def ease_out_over(t): return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
def ease_in_out_over(t):
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

# Inverted functions (mirrored along x=y linear diagonal) for fast in/out instead of slow
# Only supports monotonic formulas, smootherstep skipped due to complexity

# Helper functions
def clamp01(x): return max(0.0, min(1.0, x))

# INV_SMOOTH
def inv_ease_in_out_smooth(x): return 0.5 - math.sin(math.asin(1.0 - 2.0 * x) / 3.0)
def inv_ease_in_smooth(x): return 2.0 * inv_ease_in_out_smooth(x * 0.5)
def inv_ease_out_smooth(x): return 2.0 * inv_ease_in_out_smooth((x + 1.0) * 0.5) - 1.0

# INV_SMOOTHX
def inv_ease_in_out_smoothx(x): return inv_ease_in_out_smooth(inv_ease_in_out_smooth(x))
def inv_ease_in_smoothx(x): return 2.0 * inv_ease_in_out_smoothx(x * 0.5)
def inv_ease_out_smoothx(x): return 2.0 * inv_ease_in_out_smoothx((x + 1.0) * 0.5) - 1.0

# INV_SINE
def inv_ease_in_sine(x): return (2.0 / math.pi) * math.acos(1.0 - x)
def inv_ease_out_sine(x): return (2.0 / math.pi) * math.asin(x)
def inv_ease_in_out_sine(x): return math.acos(1.0 - 2.0 * x) / math.pi

# INV_QUAD
def inv_ease_in_quad(x): return math.sqrt(x)
def inv_ease_out_quad(x): return 1.0 - math.sqrt(1.0 - x)
def inv_ease_in_out_quad(x): return math.sqrt(x * 0.5) if x < 0.5 else 1.0 - math.sqrt((1.0 - x) * 0.5)

# INV_CUBIC
def cbrt(x): return math.copysign(abs(x) ** (1.0 / 3.0), x)
def inv_ease_in_cubic(x): return cbrt(x)
def inv_ease_out_cubic(x): return 1.0 - cbrt(1.0 - x)
def inv_ease_in_out_cubic(x): return cbrt(x * 0.25) if x < 0.5 else 1.0 - cbrt((1.0 - x) * 0.25)

# INV_QUART
def inv_ease_in_quart(x): return x ** 0.25
def inv_ease_out_quart(x): return 1.0 - ((1.0 - x) ** 0.25)
def inv_ease_in_out_quart(x): return (x / 8.0) ** 0.25 if x < 0.5 else 1.0 - ((1.0 - x) / 8.0) ** 0.25

# INV_QUINT
def inv_ease_in_quint(x): return x ** 0.2
def inv_ease_out_quint(x): return 1.0 - ((1.0 - x) ** 0.2)
def inv_ease_in_out_quint(x): return (x / 16.0) ** 0.2 if x < 0.5 else 1.0 - ((1.0 - x) / 16.0) ** 0.2

# INV_EXPO
def inv_ease_in_expo(x): return 0.0 if x <= 0.0 else clamp01((math.log2(x) + 10.0) / 10.0)
def inv_ease_out_expo(x): return 1.0 if x >= 1.0 else clamp01(-math.log2(1.0 - x) / 10.0)
def inv_ease_in_out_expo(x):
	if x <= 0.0: return 0.0
	if x >= 1.0: return 1.0
	return clamp01((math.log2(2.0 * x) + 10.0) / 20.0) if x < 0.5 else clamp01((10.0 - math.log2(2.0 * (1.0 - x))) / 20.0)

# INV_CIRC
def inv_ease_in_circ(x): return math.sqrt(1.0 - (1.0 - x) * (1.0 - x))
def inv_ease_out_circ(x): return 1.0 - math.sqrt(1.0 - x * x)
def inv_ease_in_out_circ(x): return 0.5 * math.sqrt(1.0 - (1.0 - 2.0 * x) ** 2) if x < 0.5 else 1.0 - 0.5 * math.sqrt(1.0 - (2.0 * x - 1.0) ** 2)



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
	"over": {
		"in": ease_in_over,
		"out": ease_out_over,
		"inout": ease_in_out_over
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
	},
	"inv_smooth": {
		"in": inv_ease_in_smooth,
		"out": inv_ease_out_smooth,
		"inout": inv_ease_in_out_smooth
	},
	"inv_smoothx": {
		"in": inv_ease_in_smoothx,
		"out": inv_ease_out_smoothx,
		"inout": inv_ease_in_out_smoothx
	},
	"inv_sine": {
		"in": inv_ease_in_sine,
		"out": inv_ease_out_sine,
		"inout": inv_ease_in_out_sine
	},
	"inv_quad": {
		"in": inv_ease_in_quad,
		"out": inv_ease_out_quad,
		"inout": inv_ease_in_out_quad
	},
	"inv_cubic": {
		"in": inv_ease_in_cubic,
		"out": inv_ease_out_cubic,
		"inout": inv_ease_in_out_cubic
	},
	"inv_quart": {
		"in": inv_ease_in_quart,
		"out": inv_ease_out_quart,
		"inout": inv_ease_in_out_quart
	},
	"inv_quint": {
		"in": inv_ease_in_quint,
		"out": inv_ease_out_quint,
		"inout": inv_ease_in_out_quint
	},
	"inv_expo": {
		"in": inv_ease_in_expo,
		"out": inv_ease_out_expo,
		"inout": inv_ease_in_out_expo
	},
	"inv_circ": {
		"in": inv_ease_in_circ,
		"out": inv_ease_out_circ,
		"inout": inv_ease_in_out_circ
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

#	Slot-aware F-curve access (Blender 4.4+ "Slotted Actions")
#	Blender 5.0 removed the legacy Action.fcurves API; F-curves now live on a
#	channelbag belonging to the action's assigned slot. Returns the fcurves
#	collection for the object's active action slot, or None if unavailable.
def _action_fcurves(obj):
	ad = obj.animation_data
	if not (ad and ad.action):
		return None
	cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
	return cb.fcurves if cb else None



#	curveAtTime(item name, animation curve index, sample time in frames)
#	curveAtTime("Cube", 0, frame-5)
#	returns the "Cube" object's first animation curve value 5 frames in the past
#	Blender requires an animation curve to get non-current-frame data
#	Blender doesn't reference animation curves by type or name, only numerical index
def curve_at_time(name, channel, frame):
	obj = bpy.data.objects.get(name)
	if obj is None:
		return 0.0
	fcurves = _action_fcurves(obj)
	if not fcurves or channel < 0 or channel >= len(fcurves):
		return 0.0
	return fcurves[channel].evaluate(frame)



#	ease(time, type, direction)
#	ease(frame/30, circular, inout)
#	Implements common easing functions for a value between 0 and 1
#	Expected use case is within additional math expressions to map the 0-1 range to the desired values
def ease(time, ease_type, direction, a=0, b=1):
	if time <= 0:
		return a
	elif time >= 1:
		return b
	else:
		if a == 0 and b == 1:
			return get_ease(time, ease_type, direction)
		else:
			return lerp(a, b, get_ease(time, ease_type, direction))



#	hash(string)
#	hash("string of text")
#	Returns value within the range 0 to 99999 based on the pseudo-hash of a string (deterministic based on sum ord)
def hash(string=0):
	if "{project}" in string:
		import os
		string = string.replace("{project}", os.path.splitext(os.path.basename(bpy.data.filepath))[0])
	if "{scene}" in string:
		string = string.replace("{scene}", bpy.context.scene.name)
	if "{viewlayer}" in string:
		string = string.replace("{viewlayer}", bpy.context.view_layer.name)
#	return int(sum(ord(c) for c in str(string)) * 123.456) % 99999
	return int(sum((i + 1) * ord(c) for i, c in enumerate(str(string))) % 99999)



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
	if c <= 0:
		return a
	elif c >= 1:
		return b
	else:
		return (a * (1 - c)) + (b * c)



#	Shared relative/seconds/clamp/ease/value-range tail for markerValue, markerPrev, and markerNext
#	(kept identical to the original inline blocks: seconds gating clamp/ease/lerp, relative applied first)
def _apply_time_options(frame, scene, frame_current, relative, seconds, clamp, duration, a, b, ease_type, direction):
	if relative:
		frame = frame_current - frame
	if seconds:
		frame /= scene.render.fps / scene.render.fps_base
		if clamp:
			frame = min(max(frame / duration, 0), 1)
			if ease_type != 'linear':
				frame = get_ease(frame, ease_type, direction)
		if a != 0 or b != 1:
			frame = (a * (1 - frame)) + (b * frame)
	return frame



#	markerValue(required: marker name, optional: static or relative time, frames or seconds, clamp, duration, start value, end value, easing type, easing direction)
#	markerValue('marker_1')
#	markerValue('marker_1', False, True)
#	markerValue('marker_1', True, True, True, 1.0)
#	markerValue('marker_1', True, True, True, 1.0, -0.5, 0.5, 'smooth', 'inout')
def marker_value(name, relative=False, seconds=False, clamp=False, duration=1, a=0, b=1, ease_type='linear', direction='inout'):
	scene = bpy.context.scene
	frame_by_name = _marker_snapshot(scene).frame_by_name
	if name not in frame_by_name:
		return 0
	frame = frame_by_name[name]
	return _apply_time_options(frame, scene, scene.frame_current, relative, seconds, clamp, duration, a, b, ease_type, direction)

#	markerPrev(optional: text filter, static or relative time, frames or seconds, clamp, duration, start value, end value, easing type, easing direction)
#	markerPrev('')
#	markerPrev('marker_')
#	markerPrev('marker_', False, True)
#	markerPrev('marker_', True, True, True, 1.0)
#	markerPrev('marker_', True, True, True, 1.0, -0.5, 0.5, 'smooth', 'inout')
def marker_prev(filter_str=False, relative=False, seconds=False, clamp=False, duration=1, a=0, b=1, ease_type='linear', direction='inout'):
	scene = bpy.context.scene
	frame = scene.frame_start
	snapshot = _marker_snapshot(scene)
	markers = snapshot.markers
	# Find closest marker frame at or before current frame
	if markers:
		frame_current = scene.frame_current
		if not filter_str:
			# Unfiltered: the nearest marker at or before the current frame is already precomputed
			# (-100000 when none precede the playhead, matching the original loop's fallthrough)
			frame = snapshot.active_frame
		else:
			# Filtered: largest matching frame at or before the playhead. Markers are sorted ascending,
			# so once we pass the playhead with a match already held there is nothing left to improve.
			frame = -100000
			marker_found = False
			for marker_frame, marker_name in markers:
				if marker_frame > frame_current and frame != -100000:
					break
				if filter_str in marker_name:
					marker_found = True
					if marker_frame <= frame_current:
						frame = marker_frame
			if not marker_found:
				frame = scene.frame_start
		frame = _apply_time_options(frame, scene, frame_current, relative, seconds, clamp, duration, a, b, ease_type, direction)
	return frame

#	markerNext(optional: text filter, static or relative time, frames or seconds, clamp, duration, start value, end value, easing type, easing direction)
#	markerNext()
#	markerNext('marker_')
#	markerNext('marker_', False, True)
#	markerNext('marker_', True, True, True, 1.0)
#	markerNext('marker_', True, True, True, 1.0, -0.5, 0.5, 'smooth', 'inout')
def marker_next(filter_str=False, relative=False, seconds=False, clamp=False, duration=1, a=0, b=1, ease_type='linear', direction='inout'):
	scene = bpy.context.scene
	frame = scene.frame_end
	markers = _marker_snapshot(scene).markers
	# Find closest marker frame at or after current frame
	if markers:
		frame_current = scene.frame_current
		# Markers are sorted ascending, so the first match at or after the playhead is the nearest one
		frame = 100000
		marker_found = False
		for marker_frame, marker_name in markers:
			if filter_str and filter_str not in marker_name:
				continue
			marker_found = True
			if marker_frame >= frame_current:
				frame = marker_frame
				break
		if not marker_found:
			frame = scene.frame_end
		frame = _apply_time_options(frame, scene, frame_current, relative, seconds, clamp, duration, a, b, ease_type, direction)
	return frame

#	markerRange(required: marker start, marker end, optional: mode, start value, end value, easing type, easing direction)
#	markerRange('marker_1', 'marker_2')
#	markerRange('marker_1', 'marker_2', 'extend', -0.5, 0.5)
#	markerRange('marker_1', 'marker_2', 'clamp', -0.5, 0.5, 'smooth', 'inout')
#	markerRange('marker_1', 'marker_2', 'switch', -0.5, 0.5)
#	Modes: 'extend' (default), 'clamp', 'switch'
def marker_range(start, end, mode='extend', a=0, b=1, ease_type='linear', direction='inout'):
	scene = bpy.context.scene
	frame_by_name = _marker_snapshot(scene).frame_by_name
	if start in frame_by_name and end in frame_by_name:
		start = frame_by_name[start]
		end = frame_by_name[end]
		frame_current = scene.frame_current
		# Switch: value B while inside the range, value A outside of it
		if mode == 'switch':
			return b if start <= frame_current < end else a
		# Zero-width range (two differently named markers on the same frame): avoid divide-by-zero
		if end == start:
			return b if frame_current >= start else a
		c = (frame_current - start) / (end - start)
		if mode == 'clamp':
			c = min(max(c, 0), 1)
			if ease_type != 'linear':
				c = get_ease(c, ease_type, direction)
		if a != 0 or b != 1:
			c = (a * (1.0 - c)) + (b * c)
		return c
	else:
		return 0.0

# First marker strictly after `after_frame` whose name contains `filter_str` ('' matches any)
def _next_marker_frame(markers, after_frame, filter_str=''):
	for marker_frame, marker_name in markers:
		if marker_frame > after_frame and (not filter_str or filter_str in marker_name):
			return marker_frame
	return None

# Earliest marker whose name is in names (markers is sorted by frame); None if no match
def _first_match_frame(markers, names):
	for marker_frame, marker_name in markers:
		if marker_name in names:
			return marker_frame
	return None

# Nearest match at or before the current frame, falling back to the earliest match
# so ranges extrapolate before the first occurrence; None if no match
def _active_match_frame(markers, names, frame_current):
	start = first = None
	for marker_frame, marker_name in markers:
		# Markers are sorted ascending: once past the playhead with the earliest match already found,
		# `start` can no longer change and `first` is settled, so there is nothing left to scan
		if marker_frame > frame_current and first is not None:
			break
		if marker_name in names:
			if first is None:
				first = marker_frame
			if marker_frame <= frame_current:
				start = marker_frame
	return start if start is not None else first

#	markerMatch(required: self, optional: source, filter, mode, value A, value B, easing type, easing direction)
#	markerMatch(self) = frame number of the marker exactly matching the name of the item this driver is attached to, or 0 if no marker found
#	markerMatch(self, 'collection') = matches against the name of the primary collection the item is in
#	markerMatch(self, 'collections') = matches against the name of any collection the item is in
#	markerMatch(self, 'item', 'walk_', 'frame', 0.5) = matches against the item name and the next marker that follows it that contains the specified string, returning the frame number halfway between the two markers
#	markerMatch(self, 'item', '', 'switch', 2.0, 3.0) = returns 3 if within the valid range (exact match >= current frame > next marker on timeline) and 2 if not
#	markerMatch(self, 'item', '', 'clamp', 0.0, 1.0, 'smooth', 'inout') = returns interpolation of the valid range
#	Sources: 'item' (default), 'collection', 'collections'
#	Filter: '' matches any marker as the range end (default); a string limits the range end to markers that contain the string (the exact-match start marker is never filtered)
#	Modes: 'frame' (default), 'extend', 'clamp', 'switch'
#	'frame' is a STATIC value - the first matching marker's frame, the same regardless of the current frame
#	'switch'/'extend'/'clamp' are playhead-relative - they anchor to the nearest matching marker at or before the current frame
#	Frame mode value A is a 0-1 position along the detected range: 0.0 = matched marker (default), 1.0 = next marker
#	IMPORTANT: requires "Use Self" to be toggled on in the driver settings
def marker_match(self, source='item', filter_str='', mode='frame', a=0.0, b=1.0, ease_type='linear', direction='inout'):
	scene = bpy.context.scene
	# self is the property owner; id_data resolves to the owning object (also covers bones)
	obj = getattr(self, "id_data", None)
	if obj is None:
		obj = self
	# Drivers evaluate against the depsgraph where users_collection is empty
	# The original datablock is required to read collection membership (and the true name)
	obj = getattr(obj, "original", None) or obj
	if not hasattr(obj, "name"):
		return a
	# Per-frame snapshot shared by every marker driver (see _MarkerSnapshot)
	snapshot = _marker_snapshot(scene)
	markers = snapshot.markers
	frame_current = scene.frame_current
	# Build the set of name(s) to compare against
	source = str(source).lower()
	if source == 'collections':
		names = {collection.name for collection in getattr(obj, "users_collection", ())}
	elif source == 'collection':
		collections = getattr(obj, "users_collection", ())
		names = {collections[0].name} if collections else set()
	else:
		names = {obj.name}
	mode = str(mode).lower()
	# Frame mode (default): a STATIC value - the first matching marker's frame, or a 0-1 position
	# (value A) along the range to the next marker. Independent of the current frame.
	if mode == 'frame':
		start_frame = _first_match_frame(markers, names)
		if start_frame is None:
			return 0.0
		# Position 0 (default): the matched marker frame, no range scan needed
		if a == 0.0:
			return float(start_frame)
		# Position > 0: interpolate toward the next marker (range end optionally limited by the filter)
		end_frame = _next_marker_frame(markers, start_frame, filter_str)
		if end_frame is None:
			return float(start_frame)
		return start_frame + a * (end_frame - start_frame)
	# Switch mode: value B while the playhead is inside a matched range, value A otherwise
	if mode == 'switch':
		# Unfiltered: the range ends at the very next marker, so the state is simply whether the
		# nearest marker at or before the current frame is an exact match (precomputed snapshot)
		if not filter_str:
			return b if snapshot.active_name in names else a
		# Filtered: the range ends at the next marker containing the filter, ignoring markers that
		# do not. Scan for the nearest relevant marker at or before the current frame - relevant
		# meaning an exact match (which starts a range, filter or not) or a filter match (which ends one).
		# An exact-match start marker takes precedence even when it also contains the filter string.
		nearest_is_match = None
		for marker_frame, marker_name in markers:
			if marker_frame > frame_current:
				break
			exact = marker_name in names
			if exact or filter_str in marker_name:
				nearest_is_match = exact
		return b if nearest_is_match else a
	# Extend / Clamp: map [0,1] from the active matched marker to the next marker in the timeline
	start_frame = _active_match_frame(markers, names, frame_current)
	if start_frame is None:
		return a
	# End of the range: nearest marker strictly after the start marker whose name contains
	# the filter ('' matches any). The exact-match start marker is never filtered.
	end_frame = _next_marker_frame(markers, start_frame, filter_str)
	if end_frame is None:
		return b
	c = (frame_current - start_frame) / (end_frame - start_frame)
	if mode == 'clamp':
		c = min(max(c, 0), 1)
		if ease_type != 'linear':
			c = get_ease(c, ease_type, direction)
	if a != 0 or b != 1:
		c = (a * (1.0 - c)) + (b * c)
	return c



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
# Expression builders (shared between the panel and the right-click operator)

#	Build the shortest valid markerRange() expression from the panel settings
#	(the runtime mode keyword is just the lowercase enum identifier)
def build_marker_range_expression(settings):
	start = settings.driver_marker_name
	end = settings.driver_marker_end
	mode = settings.driver_range_mode.lower()
	a = settings.driver_value_a
	b = settings.driver_value_b
	ease_type = settings.driver_ease_type
	# Extend with the default 0-1 range: shortest form (mode defaults to 'extend')
	if mode == 'extend' and a == 0 and b == 1:
		return f"markerRange('{start}', '{end}')"
	expression = f"markerRange('{start}', '{end}', '{mode}'"
	# Include the value range when custom, or when clamp easing needs it to reach the ease arguments
	if a != 0 or b != 1 or (mode == 'clamp' and ease_type != 'linear'):
		expression += f", {a}, {b}"
		if mode == 'clamp' and ease_type != 'linear':
			expression += f", '{ease_type}', '{settings.driver_ease_direction}'"
	return expression + ")"

#	Build the shortest valid markerMatch() expression from the panel settings
def build_marker_match_expression(settings):
	source = settings.driver_match_source.lower()
	filter_str = settings.driver_marker_string if settings.driver_marker_filter else ''
	mode = settings.driver_match_mode
	# Frame mode is the runtime default; value A carries the 0-1 range position
	if mode == 'FRAME':
		position = settings.driver_match_position
		# Compact forms when there is no filter and no position offset
		if filter_str == '' and position == 0.0:
			if source != 'item':
				return f"markerMatch(self, '{source}')"
			return "markerMatch(self)"
		# A position offset needs the explicit 'frame' mode to reach the value slot
		if position != 0.0:
			return f"markerMatch(self, '{source}', '{filter_str}', 'frame', {position})"
		# Filter only: filter alone is enough (mode defaults to frame)
		return f"markerMatch(self, '{source}', '{filter_str}')"
	a = settings.driver_value_a
	b = settings.driver_value_b
	# Switch mode must state 'switch' explicitly (omitting the mode would fall back to 'frame')
	if mode == 'SWITCH':
		if a != 0.0 or b != 1.0:
			return f"markerMatch(self, '{source}', '{filter_str}', 'switch', {a}, {b})"
		return f"markerMatch(self, '{source}', '{filter_str}', 'switch')"
	# Extend / Clamp ramp between the matched marker and the next one
	# (the runtime mode keyword is just the lowercase enum identifier)
	expression = f"markerMatch(self, '{source}', '{filter_str}', '{mode.lower()}', {a}, {b}"
	if mode == 'CLAMP' and settings.driver_ease_type != 'linear':
		expression += f", '{settings.driver_ease_type}', '{settings.driver_ease_direction}'"
	return expression + ")"



###########################################################################
# Legacy driver migration (older marker driver argument formats -> current format)

#	Rewrite legacy markerRange() and markerMatch() calls to the	current argument order
#	`markerRange` 3rd positional arg: legacy bool clamp -> 'extend' / 'clamp' mode string
#	`markerMatch` legacy value form markerMatch(self, 'src', a[, b]) with a numeric third argument -> markerMatch(self, 'src', 'switch', a[, b]), preserving the old 0/1 style
#	`markerMatch` gained a filter (range-end) string between source and mode. Legacy mode-bearing calls
#	markerMatch(self, 'src', 'mode', ...) predate it, so an empty filter '' is inserted -> markerMatch(self, 'src', '', 'mode', ...).
#	Detection: the mode slot holds a known mode keyword and the arg after it is not also a mode keyword (which would mean the
#	string is already a filter). A brand-new filter string that happens to equal a mode keyword with no explicit mode after it
#	(e.g. markerMatch(self, 'item', 'clamp')) is indistinguishable from the legacy form and would be rewritten - avoid mode words as filters.
#	When match_switch is True, the plain forms markerMatch(self) and markerMatch(self, 'src') also gain an explicit 'switch' mode. These are ambiguous (they are valid new frame-mode syntax too), so this is opt-in for upgrading a project made before Marker Match gained output modes, where those forms always meant Switch.

_MARKER_MATCH_MODES = ('frame', 'extend', 'clamp', 'switch')

def _migrate_marker_expression(expr, match_switch=False):
	try:
		tree = ast.parse(expr, mode='eval')
	except SyntaxError:
		return expr, False
	changed = False
	for node in ast.walk(tree):
		if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
			continue
		if node.func.id == 'markerRange' and len(node.args) >= 3:
			a3 = node.args[2]
			if isinstance(a3, ast.Constant) and isinstance(a3.value, bool):
				node.args[2] = ast.Constant('clamp' if a3.value else 'extend')
				changed = True
		elif node.func.id == 'markerMatch':
			args = node.args
			# Step 1: pre-modes value form (numeric mode slot) -> explicit 'switch' mode
			if len(args) >= 3:
				a3 = args[2]
				# A numeric third argument is the legacy value slot; a string there is already a mode
				if isinstance(a3, ast.Constant) and isinstance(a3.value, (int, float)) and not isinstance(a3.value, bool):
					args.insert(2, ast.Constant('switch'))
					changed = True
			elif match_switch:
				# Plain pre-modes forms: markerMatch(self) / markerMatch(self, 'src') -> explicit Switch
				if len(args) == 1:
					args.append(ast.Constant('item'))
					args.append(ast.Constant('switch'))
					changed = True
				elif len(args) == 2 and isinstance(args[1], ast.Constant) and isinstance(args[1].value, str):
					args.append(ast.Constant('switch'))
					changed = True
			# Step 2: pre-filter forms carry the mode in the filter slot -> insert an empty filter ahead of it
			if len(args) >= 3:
				a3 = args[2]
				a4 = args[3] if len(args) >= 4 else None
				third_is_mode = isinstance(a3, ast.Constant) and a3.value in _MARKER_MATCH_MODES
				fourth_is_mode = isinstance(a4, ast.Constant) and a4.value in _MARKER_MATCH_MODES
				if third_is_mode and not fourth_is_mode:
					args.insert(2, ast.Constant(''))
					changed = True
	if not changed:
		return expr, False
	ast.fix_missing_locations(tree)
	return ast.unparse(tree.body), True

#	Return every driver in the file and de-duplicated
def _iter_drivers():
	seen = set()
	sources = [
		bpy.data.objects,
		bpy.data.materials,
		bpy.data.node_groups,
		bpy.data.scenes,
		bpy.data.worlds,
		bpy.data.lights,
		bpy.data.cameras,
		bpy.data.meshes,
		bpy.data.curves,
		bpy.data.metaballs,
		bpy.data.lattices,
		bpy.data.armatures,
		bpy.data.speakers,
		bpy.data.textures,
	]
	for collection in sources:
		for data_item in collection:
			ad = getattr(data_item, "animation_data", None)
			if ad and ad.drivers:
				for fcurve in ad.drivers:
					driver = fcurve.driver
					if driver and driver.as_pointer() not in seen:
						seen.add(driver.as_pointer())
						yield data_item, fcurve, driver



###########################################################################
# Action classes

class CopyDriverToClipboard(bpy.types.Operator):
	"""Copy the specified string to the clipboard"""
	bl_idname = "object.copy_to_clipboard"
	bl_label = "Copy Text"
	
	string: bpy.props.StringProperty(default="")
	
	def execute(self, context):
		context.window_manager.clipboard = self.string
		return {'FINISHED'}



class PRODUCTIONKIT_OT_add_marker_match_driver(bpy.types.Operator):
	"""Add a Marker Match driver to the property under the cursor, using the current Driver Functions settings, with Use Self enabled"""
	bl_idname = "productionkit.add_marker_match_driver"
	bl_label = "Add Marker Match Driver"
	bl_options = {'REGISTER', 'UNDO'}
	
	# Optional explicit expression; when empty the expression is built from panel settings
	expression: bpy.props.StringProperty(default="")
	
	@classmethod
	def poll(cls, context):
		# Only valid over a property (right-click context menu on a driveable value)
		return getattr(context, "property", None) is not None
	
	@staticmethod
	def build_expression(context):
		return build_marker_match_expression(context.scene.production_kit_settings)
	
	def execute(self, context):
		prop = getattr(context, "property", None)
		if not prop:
			self.report({'ERROR'}, "No property under the cursor - right-click a value to use this")
			return {'CANCELLED'}
		id_block, data_path, array_index = prop
		if id_block is None:
			self.report({'ERROR'}, "This property has no datablock that can hold a driver")
			return {'CANCELLED'}
		
		expression = self.expression or self.build_expression(context)
		
		# Add the driver, retrying across all channels if the reported index is rejected
		try:
			try:
				result = id_block.driver_add(data_path, array_index)
			except (TypeError, RuntimeError):
				result = id_block.driver_add(data_path)
		except Exception as exc:
			self.report({'ERROR'}, f"Could not add driver: {exc}")
			return {'CANCELLED'}
		
		fcurves = result if isinstance(result, list) else [result]
		for fcurve in fcurves:
			driver = fcurve.driver
			driver.type = 'SCRIPTED'
			driver.use_self = True
			driver.expression = expression
		
		id_block.update_tag()
		self.report({'INFO'}, f"Added driver: {expression}")
		return {'FINISHED'}



class WM_OT_find_replace_marker_expression(bpy.types.Operator):
	"""Find and replace string in all marker names and driver expressions"""
	bl_idname = "wm.find_replace_marker_expression"
	bl_label = "Replace Marker Names & Driver Expressions"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		settings = context.scene.production_kit_settings
		find = settings.driver_marker_find
		replace = settings.driver_marker_replace
		
		# Statistics
		markers_modified = 0
		drivers_modified = 0
		
		# Process all timeline markers
		if bpy.context.scene.timeline_markers:
			for marker in bpy.context.scene.timeline_markers:
				if find in marker.name:
					marker.name = marker.name.replace(find, replace)
					markers_modified += 1
					print(f"Modified marker: {marker.name}")
		
		# Process every driver in the file (single de-duplicated walk across all datablock types)
		for data_item, fcurve, driver in _iter_drivers():
			expression = driver.expression
			if expression and find in expression:
				driver.expression = expression.replace(find, replace)
				drivers_modified += 1
				print(f"Modified driver on {data_item.name}: {fcurve.data_path}")
		
		# Print summary
		print(f"\n--- Find & Replace Complete ---")
		print(f"Search string: '{find}'")
		print(f"Replace string: '{replace}'")
		print(f"Markers modified: {markers_modified}")
		print(f"Drivers modified: {drivers_modified}")
		print(  f"-------------------------------\n")
		
		return {'FINISHED'}



class WM_OT_update_legacy_drivers(bpy.types.Operator):
	"""Update legacy driver expressions in this file to the current argument format (currently Marker Range and Marker Match).\nSafe to run more than once; only outdated expressions are changed"""
	bl_idname = "wm.update_legacy_drivers"
	bl_label = "Update Legacy Drivers"
	bl_options = {'REGISTER', 'UNDO'}

	match_switch: bpy.props.BoolProperty(
		name="Plain Match → Switch",
		description="Also treat markerMatch(self) and markerMatch(self, 'source') as Switch drivers and append 'switch'. Enable when upgrading a project made before Marker Match had output modes (where these always meant Switch); leave off for files that intentionally use the new Frame mode",
		default=True)

	def invoke(self, context, event):
		# Rewrites expressions across the whole file, so confirm (and expose the option) before running
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		col = self.layout.column()
		col.prop(self, "match_switch")

	def execute(self, context):
		scanned = 0
		updated = 0
		for data_item, fcurve, driver in _iter_drivers():
			expression = driver.expression
			if not expression or ('markerRange' not in expression and 'markerMatch' not in expression):
				continue
			scanned += 1
			new_expression, changed = _migrate_marker_expression(expression, self.match_switch)
			if changed:
				driver.expression = new_expression
				updated += 1
				print(f"Updated driver on {data_item.name}: {fcurve.data_path} -> {new_expression}")
		
		print(f"\n--- Legacy Driver Update Complete ---")
		print(f"Legacy drivers scanned: {scanned}")
		print(f"Drivers updated: {updated}")
		print(  f"-------------------------------------\n")

		self.report({'INFO'}, f"Updated {updated} of {scanned} legacy driver(s)")
		return {'FINISHED'}



#	Return (datablock, data_path, array_index, expression) for every driver orphaned after a property or node socket is removed
def _iter_orphaned_drivers():
	for data_item, fcurve, driver in _iter_drivers():
		try:
			# Driver data paths resolve relative to their owning datablock
			data_item.path_resolve(fcurve.data_path)
		except Exception:
			yield data_item, fcurve.data_path, fcurve.array_index, driver.expression



class WM_OT_delete_orphaned_drivers(bpy.types.Operator):
	"""Find and delete drivers whose target property no longer exists (orphaned when a property or node socket is removed). Lists everything for review before deleting"""
	bl_idname = "wm.delete_orphaned_drivers"
	bl_label = "Delete Orphaned Drivers"
	bl_options = {'REGISTER', 'UNDO'}
	
	# How many entries to spell out in the confirmation dialog before summarising the rest
	_display_limit = 20
	
	def invoke(self, context, event):
		# Scan up front so the confirmation dialog can list exactly what will be removed
		self._orphans = list(_iter_orphaned_drivers())
		if not self._orphans:
			self.report({'INFO'}, "No orphaned drivers found")
			return {'CANCELLED'}
		return context.window_manager.invoke_props_dialog(self, width=520)
	
	def draw(self, context):
		layout = self.layout
		orphans = getattr(self, "_orphans", [])
		layout.label(text=f"Delete {len(orphans)} orphaned driver(s)?", icon='TRASH')
		box = layout.box().column(align=True)
		for data_item, data_path, array_index, expression in orphans[:self._display_limit]:
			box.label(text=f"{data_item.name}  —  {data_path}[{array_index}]", icon='DRIVER')
		remainder = len(orphans) - self._display_limit
		if remainder > 0:
			box.label(text=f"…and {remainder} more")
	
	def execute(self, context):
		removed = 0
		done = set()
		for data_item, data_path, array_index, expression in getattr(self, "_orphans", []):
			# Deduplicate per (datablock, path): one call clears every channel of that path
			key = (data_item.as_pointer(), data_path)
			if key in done:
				continue
			done.add(key)
			try:
				# driver_remove matches the stored data path string, so unresolvable paths still clear
				if data_item.driver_remove(data_path, -1):
					removed += 1
					print(f"Removed orphaned driver on {data_item.name}: {data_path} -> {expression!r}")
			except Exception as exc:
				print(f"Could not remove driver on {data_item.name}: {data_path} ({exc})")
		
		print(f"\n--- Orphaned Driver Cleanup ---")
		print(f"Orphaned drivers removed: {removed}")
		print(  f"-------------------------------\n")
		
		self.report({'INFO'}, f"Removed {removed} orphaned driver(s)")
		return {'FINISHED'}





###########################################################################
# UI rendering classes

class PRODUCTIONKIT_PT_driverFunctions(bpy.types.Panel):
	bl_label = "Driver Functions"
	bl_idname = "PRODUCTIONKIT_PT_driverFunctions"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = 'Launch'
	bl_order = 24
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "drivers_category"
	
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
			
			# Warning tracker
			warn = ''
			
			# Info tracker
			info = ''
			
			# Curve At Time
			if settings.driver_select == 'CURVE':
				if context.active_object:
					obj = context.active_object
					if _action_fcurves(obj):
						col.prop(settings, 'driver_curve_channel')
						col.prop(settings, 'driver_curve_offset')
						
						driver = f"curveAtTime('{context.active_object.name}', {settings.driver_curve_channel}, {settings.driver_curve_offset})"
					else:
						error = 'no animation curves'
				else:
					error = 'no active object'
			
			# Ease
			elif settings.driver_select == 'EASE':
				row1 = col.row(align=True)
				row1.prop(settings, 'driver_value_t', text='')
				row1.prop(settings, 'driver_ease_type', text='')
				row1.prop(settings, 'driver_ease_direction', text='')
				
				driver = f"ease({settings.driver_value_t}, '{settings.driver_ease_type}', '{settings.driver_ease_direction}')"
			
			# Hash
			elif settings.driver_select == 'HASH':
				row1 = col.row(align=True)
				row1.prop(settings, 'driver_var_project', toggle=1)
				row1.prop(settings, 'driver_var_scene', toggle=1)
				row1.prop(settings, 'driver_var_viewlayer', toggle=1)
				
				driver = "hash('"
				if not (settings.driver_var_project or settings.driver_var_scene or settings.driver_var_viewlayer):
					driver += "string"
				else:
					if settings.driver_var_project:
						driver += "{project}"
					if settings.driver_var_scene:
						driver += "{scene}"
					if settings.driver_var_viewlayer:
						driver += "{viewlayer}"
				driver += "')"
			
			# Lerp
			elif settings.driver_select == 'LERP':
				row1 = col.row(align=True)
				row1.prop(settings, 'driver_value_a')
				row1.prop(settings, 'driver_value_b')
				row1.prop(settings, 'driver_value_c')
				
				driver = f"lerp({settings.driver_value_a}, {settings.driver_value_b}, {settings.driver_value_c})"
			
			# Marker Range
			elif settings.driver_select == 'MARKER-RANGE':
				if context.scene.timeline_markers:
					mode = settings.driver_range_mode
					
					# Marker selection
					col.prop_search(settings, "driver_marker_name", context.scene, "timeline_markers", text="")
					col.prop_search(settings, "driver_marker_end", context.scene, "timeline_markers", text="")
					col.separator()
					
					# Mode (Extend / Clamp / Switch)
					rowA = col.row(align=True)
					rowA.prop(settings, 'driver_range_mode', expand=True)
					
					# Value range UI
					rowB = col.row(align=True)
					rowB.prop(settings, 'driver_value_a', text="")
					rowB.prop(settings, 'driver_value_b', text="")
					
					# Interpolation UI (only meaningful when clamped)
					rowC = col.row(align=True)
					if mode != 'CLAMP':
						rowC.active = False
						rowC.enabled = False
					rowC.prop(settings, 'driver_ease_type', text="")
					rowC.prop(settings, 'driver_ease_direction', text="")
					
					if settings.driver_marker_name == '' or settings.driver_marker_end == '':
						error = 'missing marker name'
					elif settings.driver_marker_name == settings.driver_marker_end:
						error = 'duplicate marker name'
					else:
						driver = build_marker_range_expression(settings)
				else:
					error = 'no scene markers'
			
			# Marker Match
			elif settings.driver_select == 'MARKER-MATCH':
				if context.scene.timeline_markers:
					
					# Match source (Item / Collection / Collections)
					row1 = col.row(align=True)
					row1.prop(settings, 'driver_match_source', expand=True)
					col.separator()
					
					# Range filtering
					row2 = col.row(align=True)
					row2.prop(settings, 'driver_marker_filter', text='Range Filter', toggle=True)
					option = row2.column(align=True)
					if not settings.driver_marker_filter:
						option.active = False
						option.enabled = False
					option.prop(settings, 'driver_marker_string', text='')
					col.separator()
					
					# Value mode (Frame / Extend / Clamp / Switch)
					rowA = col.row(align=True)
					rowA.prop(settings, 'driver_match_mode', expand=True)
					
					mode = settings.driver_match_mode
					
					# Value range UI (unused for Frame mode)
					rowB = col.row(align=True)
					if mode == 'FRAME':
						rowB.prop(settings, 'driver_match_position', text="", slider=True)
					else:
						rowB.prop(settings, 'driver_value_a', text="")
						rowB.prop(settings, 'driver_value_b', text="")
					
					# Interpolation UI (only meaningful when clamped)
					rowC = col.row(align=True)
					if mode != 'CLAMP':
						rowC.active = False
						rowC.enabled = False
					rowC.prop(settings, 'driver_ease_type', text="")
					rowC.prop(settings, 'driver_ease_direction', text="")
#					col.separator()
					
#					box = col.box().column(align=True)
#					box.label(text="Requires 'Use Self' in driver", icon='STATUS_WARNING_FILLED') # STATUS_WARNING STATUS_WARNING_FILLED WARNING_LARGE
#					box.label(text="Right-click property field to 'Add Marker Match Driver'", icon='INFO') # INFO STATUS_INFO STATUS_INFO_FILLED INFO_LARGE
					warn = "Requires 'Use Self' in driver"
					info = "Right-click property to 'Add Marker Match Driver'"
					
					# Generate shortest allowed version of the driver string
					driver = build_marker_match_expression(settings)
				else:
					error = 'no scene markers'
			
			# All other marker-based drivers
			elif 'MARKER-' in settings.driver_select:
				if context.scene.timeline_markers:
					# Settings
					relative = True if settings.driver_marker_relative == 'RELATIVE' else False
					seconds = True if settings.driver_marker_seconds == 'SECONDS' else False
					clamp = True if settings.driver_marker_clamp == 'CLAMP' else False
					duration = settings.driver_marker_duration
					valueA = settings.driver_value_a
					valueB = settings.driver_value_b
					
					# Marker Value
					if settings.driver_select == 'MARKER-VALUE':
						# Marker selection
						col.prop_search(settings, "driver_marker_name", context.scene, "timeline_markers", text="")
						col.separator()
						
						# Time settings
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
						
						if settings.driver_marker_name == '':
							error = 'missing marker name'
						else:
							# Short version for basic usage (interpolation added below)
							driver = f"markerValue('{settings.driver_marker_name}'"
					
					# Marker Next and Marker Previous
					elif settings.driver_select in ['MARKER-PREV', 'MARKER-NEXT']:
						# Marker selection
						row1 = col.row(align=True)
						row1.prop(settings, 'driver_marker_filter', toggle=True)
						option = row1.column(align=True)
						if not settings.driver_marker_filter:
							option.active = False
							option.enabled = False
						option.prop(settings, 'driver_marker_string', text='')
						col.separator()
						
						# Time settings
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
						
						direction = 'markerPrev' if settings.driver_select == 'MARKER-PREV' else 'markerNext'
						string = settings.driver_marker_string if settings.driver_marker_filter else ''
						
						driver = f"{direction}('{string}'"
					
					# Menu Error
					else:
						error = 'invalid menu selection'
					
					# Value range UI
					rowA = col.row(align=True)
					if not (relative and seconds and clamp):
						rowA.active = False
						rowA.enabled = False
					rowA.prop(settings, 'driver_marker_duration', text='')
					rowA.prop(settings, 'driver_value_a', text="")
					rowA.prop(settings, 'driver_value_b', text="")
					
					# Interpolation UI
					rowB = col.row(align=True)
					if not (relative and seconds and clamp):
						rowB.active = False
						rowB.enabled = False
					rowB.prop(settings, 'driver_ease_type', text="")
					rowB.prop(settings, 'driver_ease_direction', text="")
					
					# Relative and seconds
					if relative or seconds:
						driver += f", {relative}"
						if seconds:
							driver += f", {seconds}"
					
					# Clamp, duration, and interpolation
					if relative and seconds and clamp:
						driver += f", {clamp}, {duration}"
						
						# Get interpolation type
						easeType = settings.driver_ease_type
						linear = True if easeType == "linear" else False
						
						# We have to provide a range if the values are custom, regardless of interpolation type
						# But if we don't need interpolation, just the range alone is fine
						if valueA != 0 or valueB != 1 or not linear:
							driver += f", {valueA}, {valueB}"
							if not linear:
								driver += f", '{easeType}', '{settings.driver_ease_direction}'"
					
					# Complete driver with parenthetical closing
					driver += ")"
				
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
			button = layout.column(align=True)
			text = '#' + driver
			icon = 'COPYDOWN' # COPYDOWN PASTEDOWN
			if len(error) > 0:
				text = error
				icon = 'ERROR' # ERROR CANCEL
				button.active = False
				button.enabled = False
			ops = button.operator(CopyDriverToClipboard.bl_idname, text=text, icon=icon)
			ops.string = text
			
			if len(warn) > 0 or len(info) > 0:
				box = button.box().column(align=True)
				if len(warn) > 0:
					box.label(text=warn, icon='STATUS_WARNING_FILLED') # STATUS_WARNING STATUS_WARNING_FILLED WARNING_LARGE
				if len(info) > 0:
					box.label(text=info, icon='INFO') # INFO STATUS_INFO STATUS_INFO_FILLED INFO_LARGE
		
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Driver Functions panel")



class PRODUCTIONKIT_PT_driverFunctions_find_replace(bpy.types.Panel):
	bl_label = "Utilities"
	bl_idname = "PRODUCTIONKIT_PT_driverFunctions_find_replace"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_parent_id = "PRODUCTIONKIT_PT_driverFunctions"
	bl_options = {'DEFAULT_CLOSED'}
	# Subpanel of PRODUCTIONKIT_PT_driverFunctions, so it follows the same preference
	category_preference = "drivers_category"
	
	@classmethod
	def poll(cls, context):
		# General driver-maintenance utilities, so always available under Driver Functions
		return True
	
	def draw_header(self, context):
		try:
			layout = self.layout
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Driver Functions Utilities subpanel header")
	
	def draw(self, context):
		try:
			settings = context.scene.production_kit_settings
			col = self.layout.column(align=True)
			row = col.row(align=True)
			row.prop(settings, 'driver_marker_find', text='')
			row.prop(settings, 'driver_marker_replace', text='')
			row = col.row(align=True)
			row.operator(WM_OT_find_replace_marker_expression.bl_idname, icon='ZOOM_ALL') # ZOOM_ALL VIEWZOOM SORTBYEXT
			col.separator()
			
			# Upgrade outdated driver expressions to the current format
			row = col.row(align=True)
			row.operator(WM_OT_update_legacy_drivers.bl_idname, icon='FILE_REFRESH')
			col.separator()
			
			# Remove drivers where their target property no longer exists (common with Geometry Nodes systems)
			row = col.row(align=True)
			row.operator(WM_OT_delete_orphaned_drivers.bl_idname, icon='TRASH')
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Driver Functions Utilities subpanel")





###########################################################################
# Addon registration functions

# Register custom functions in Blender's driver namespace
def production_kit_driver_functions():
	dns = bpy.app.driver_namespace
	dns["curveAtTime"] = curve_at_time
	dns["ease"] = ease
	dns["hash"] = hash
	dns["hsv"] = hsv
	dns["lerp"] = lerp
#	dns["mix"] = lerp
	dns["markerValue"] = marker_value
	dns["markerRange"] = marker_range
	dns["markerPrev"] = marker_prev
	dns["markerNext"] = marker_next
	dns["markerMatch"] = marker_match
	dns["random"] = random
	dns["wiggle"] = wiggle

# Persistent handler to register custom functions after file load
@persistent
def load_handler(dummy):
	# A new file has different scenes and markers; drop any stale snapshots
	_marker_snapshot_cache.clear()
	production_kit_driver_functions()

# Property right-click menu entry: one-click apply of a Marker Match driver
def marker_match_context_menu(self, context):
	if getattr(context, "property", None) is not None:
		layout = self.layout
		layout.separator()
		layout.operator(PRODUCTIONKIT_OT_add_marker_match_driver.bl_idname, icon='DRIVER')

classes = [
	CopyDriverToClipboard,
	PRODUCTIONKIT_OT_add_marker_match_driver,
	WM_OT_find_replace_marker_expression,
	WM_OT_update_legacy_drivers,
	WM_OT_delete_orphaned_drivers
]

# Registered from the tab category set in the extension preferences, parent panel first
panels = [
	PRODUCTIONKIT_PT_driverFunctions,
	PRODUCTIONKIT_PT_driverFunctions_find_replace,
]

def register():
	# Register classes
	for cls in classes:
		bpy.utils.register_class(cls)
	# Register panels
	utility_panel.register_panels(panels)
	# Add drivers
	production_kit_driver_functions()
	bpy.app.handlers.load_post.append(load_handler)
	# Add the one-click driver entry to the property right-click menu
	bpy.types.UI_MT_button_context_menu.append(marker_match_context_menu)

def unregister():
	# Remove the property right-click menu entry
	bpy.types.UI_MT_button_context_menu.remove(marker_match_context_menu)
	# Remove drivers
	if load_handler in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(load_handler)
	_marker_snapshot_cache.clear()
	# Unregister panels
	utility_panel.unregister_panels(panels)
	# Unregister classes
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	try:
		unregister()
	except Exception:
		pass
	register()
