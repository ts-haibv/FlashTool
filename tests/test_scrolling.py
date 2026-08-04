import unittest

from flash_tool.ui.scrolling import WheelScrollManager, normalize_wheel_units


class FakeRoot:
    def __init__(self):
        self.bindings = []
        self.unbound = []

    def bind_all(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback, add))
        return f"binding-{len(self.bindings)}"

    def _unbind(self, binding, binding_id):
        self.unbound.append((binding, binding_id))


class FakeCanvas:
    def __init__(self, first=0.0, last=1.0):
        self.first = first
        self.last = last
        self.scrolled = []

    def yview(self):
        return self.first, self.last

    def yview_scroll(self, units, what):
        self.scrolled.append((units, what))


class FakeWidget:
    def __init__(self, master=None, canvas=None):
        self.master = master
        self._parent_canvas = canvas


class FakeEvent:
    def __init__(self, widget, delta=0, num=None):
        self.widget = widget
        self.delta = delta
        self.num = num


class TestWheelScrolling(unittest.TestCase):
    def test_normalizes_windows_and_linux_wheel_events(self):
        self.assertEqual(normalize_wheel_units(120), -1)
        self.assertEqual(normalize_wheel_units(-240), 2)
        self.assertEqual(normalize_wheel_units(0, 4), -1)
        self.assertEqual(normalize_wheel_units(0, 5), 1)
        self.assertEqual(normalize_wheel_units(1), -1)

    def test_scrolls_inner_frame_before_registered_parent(self):
        root = FakeRoot()
        manager = WheelScrollManager(root)
        outer_canvas = FakeCanvas(first=0.2, last=0.8)
        inner_canvas = FakeCanvas(first=0.0, last=1.0)
        outer = FakeWidget(canvas=outer_canvas)
        inner = FakeWidget(master=outer, canvas=inner_canvas)
        manager.register(outer)
        manager.register(inner)

        self.assertTrue(manager.scroll(inner, 1))
        self.assertEqual(inner_canvas.scrolled, [])
        self.assertEqual(outer_canvas.scrolled, [(1, "units")])

    def test_scrolls_inner_frame_when_it_has_room(self):
        root = FakeRoot()
        manager = WheelScrollManager(root)
        outer_canvas = FakeCanvas(first=0.2, last=0.8)
        inner_canvas = FakeCanvas(first=0.2, last=0.8)
        outer = FakeWidget(canvas=outer_canvas)
        inner = FakeWidget(master=outer, canvas=inner_canvas)
        manager.register(outer)
        manager.register(inner)

        self.assertTrue(manager.scroll(inner, -1))
        self.assertEqual(inner_canvas.scrolled, [(-1, "units")])
        self.assertEqual(outer_canvas.scrolled, [])

    def test_wheel_uses_last_clicked_list_after_pointer_leaves(self):
        root = FakeRoot()
        manager = WheelScrollManager(root)
        canvas = FakeCanvas(first=0.2, last=0.8)
        target = FakeWidget(canvas=canvas)
        manager.register(target)

        manager._remember_target(FakeEvent(target))
        result = manager._on_wheel(FakeEvent(object(), delta=120))

        self.assertEqual(result, "break")
        self.assertEqual(canvas.scrolled, [(-1, "units")])

    def test_wheel_bubbles_to_parent_when_pointer_list_is_at_boundary(self):
        root = FakeRoot()
        manager = WheelScrollManager(root)
        outer_canvas = FakeCanvas(first=0.2, last=0.8)
        inner_canvas = FakeCanvas(first=0.0, last=1.0)
        outer = FakeWidget(canvas=outer_canvas)
        inner = FakeWidget(master=outer, canvas=inner_canvas)
        manager.register(outer)
        manager.register(inner)

        result = manager._on_wheel(FakeEvent(inner, delta=-120))

        self.assertEqual(result, "break")
        self.assertEqual(inner_canvas.scrolled, [])
        self.assertEqual(outer_canvas.scrolled, [(1, "units")])

    def test_destroy_removes_all_manager_bindings(self):
        root = FakeRoot()
        manager = WheelScrollManager(root)

        manager.destroy()

        self.assertEqual(len(root.unbound), len(manager._bound_sequences))
        self.assertEqual(
            [entry[0][2] for entry in root.unbound],
            list(manager._bound_sequences),
        )


if __name__ == "__main__":
    unittest.main()
