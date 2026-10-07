"""Check measured aliases without concealing stale-instance ambiguity."""

from dataclasses import replace
import unittest

from robots.libero.v5_public_fixture_identity import canonical_fixture_scene
from robots.libero.v5_state import Entity


def box(eid, name, lo, hi, *, visible=True, step=5, parent=None, geometry=None):
    return Entity(eid, name, tuple((a+b)/2 for a,b in zip(lo,hi)), lo, hi,
                  visible=visible, source_step=step, part_of=parent, geometry=geometry)


class PublicFixtureIdentityTests(unittest.TestCase):
    def setUp(self):
        self.cabinet = box("parent", "cabinet", (-.13, -.36, .92), (.13, -.08, 1.127))
        self.top = box("top", "cabinet top surface", (-.13, -.36, 1.12), (.13, -.08, 1.127),
                       parent="parent", geometry="measured_top_surface")
        self.thin = box("thin", "drawer", (-.12, -.35, 1.125), (.12, -.23, 1.127),
                        visible=False, step=0)

    def test_thin_surface_alias_is_removed_without_new_geometry(self):
        source = {e.id:e for e in (self.cabinet,self.top,self.thin)}
        result, evidence = canonical_fixture_scene(source,5)
        self.assertEqual(set(result), {"parent","top"})
        self.assertIn("thin",source)
        self.assertFalse(evidence["new_geometry_created"])

    def test_thick_drawer_not_rejected(self):
        drawer=replace(self.thin,lower=(-.12,-.35,1.06))
        result,_=canonical_fixture_scene([self.cabinet,self.top,drawer],5)
        self.assertIn("thin",result)

    def test_unmeasured_surface_does_not_authorize_rejection(self):
        result,_=canonical_fixture_scene([self.cabinet,replace(self.top,geometry=None),self.thin],5)
        self.assertIn("thin",result)

    def test_stale_surface_does_not_authorize_rejection(self):
        result,_=canonical_fixture_scene([self.cabinet,replace(self.top,source_step=0),self.thin],5)
        self.assertIn("thin",result)

    def test_ambiguous_surface_does_not_authorize_rejection(self):
        result,_=canonical_fixture_scene([self.cabinet,self.top,replace(self.top,id="another"),self.thin],5)
        self.assertIn("thin",result)

    def test_separate_horizontal_drawer_is_retained(self):
        drawer=replace(self.thin,lower=(.2,-.35,1.125),upper=(.4,-.23,1.127))
        result,_=canonical_fixture_scene([self.cabinet,self.top,drawer],5)
        self.assertIn("thin",result)

    def test_stale_cabinet_kept_without_independent_drawer(self):
        fragment=box("fragment","cabinet",(-.12,-.15,.922),(.12,.01,.984),visible=False,step=0)
        result,_=canonical_fixture_scene([self.cabinet,self.top,fragment],5)
        self.assertIn("fragment",result)

    def test_independent_current_drawer_can_remove_fragment_and_parts(self):
        fragment=box("fragment","cabinet",(-.12,-.15,.922),(.12,.01,.984),visible=False,step=0)
        drawer=replace(fragment,id="drawer",name="drawer",visible=True,source_step=5)
        part=replace(self.top,id="false_top",part_of="fragment",source_step=0)
        result,evidence=canonical_fixture_scene([self.cabinet,self.top,fragment,drawer,part],5,
                                               allow_drawer_fragment_alias=True)
        self.assertNotIn("fragment",result)
        self.assertNotIn("false_top",result)
        self.assertIn("drawer",result)
        self.assertFalse(evidence["selected_id_retargeted"])

    def test_stale_drawer_cannot_remove_fragment(self):
        fragment=box("fragment","cabinet",(-.12,-.15,.922),(.12,.01,.984),visible=False,step=0)
        drawer=replace(fragment,id="drawer",name="drawer",source_step=0)
        result,_=canonical_fixture_scene([self.cabinet,fragment,drawer],5,allow_drawer_fragment_alias=True)
        self.assertIn("fragment",result)

    def test_ambiguous_parent_preserves_fragment(self):
        fragment=box("fragment","cabinet",(-.12,-.15,.922),(.12,.01,.984),visible=False,step=0)
        drawer=replace(fragment,id="drawer",name="drawer",visible=True,source_step=5)
        result,_=canonical_fixture_scene([self.cabinet,replace(self.cabinet,id="other"),fragment,drawer],5,
                                         allow_drawer_fragment_alias=True)
        self.assertIn("fragment",result)

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            canonical_fixture_scene([self.cabinet,self.cabinet],5)


if __name__ == "__main__":
    unittest.main()
