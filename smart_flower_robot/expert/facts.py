"""
expert/facts.py
===============
Experta Fact definitions for the Smart Flower Robot expert system.

Each Fact class represents a piece of domain knowledge that the
KnowledgeEngine reasons about.  Facts are declared (asserted) into
the engine's working memory, and Rules pattern-match against them.

Fact catalogue
--------------
GridFact             – grid dimensions
WarehouseFact        – warehouse position
RobotFact            – robot's current position
PavilionFact         – a single pavilion's metadata
CurrentStateFact     – reference to the full State being expanded
GeneratedStateFact   – a successor state produced by a rule
GoalFact             – declares that the goal has been reached
ViolationFact        – records a rule violation / rejected action
ActionFact           – a proposed action (used for logging / display)
"""

from experta import Fact, Field


class GridFact(Fact):
    """Grid dimensions."""
    width = Field(int, mandatory=True)
    height = Field(int, mandatory=True)


class WarehouseFact(Fact):
    """Warehouse location on the grid."""
    x = Field(int, mandatory=True)
    y = Field(int, mandatory=True)


class RobotFact(Fact):
    """Robot's current position and load status."""
    x = Field(int, mandatory=True)
    y = Field(int, mandatory=True)
    has_load = Field(bool, mandatory=True)


class PavilionFact(Fact):
    """A pavilion's identity and position."""
    pid = Field(str, mandatory=True)
    flower_type = Field(str, mandatory=True)
    x = Field(int, mandatory=True)
    y = Field(int, mandatory=True)


class CurrentStateFact(Fact):
    """Reference ID to the full State object being expanded.

    The actual State is stored in the engine's ``current_state`` attribute;
    this fact just carries the id so rules can match on it.
    """
    state_id = Field(int, mandatory=True)


class GeneratedStateFact(Fact):
    """Marks that a new successor state has been generated.

    Used by the print-generated-state rule to log / display successors.
    """
    state_id = Field(int, mandatory=True)
    action = Field(str, mandatory=True)


class GoalFact(Fact):
    """Asserted when the current state satisfies the goal condition."""
    state_id = Field(int, mandatory=True)


class ViolationFact(Fact):
    """Records a rejected / invalid action with its reason."""
    parent_id = Field(int, mandatory=True)
    action = Field(str, mandatory=True)
    reason = Field(str, mandatory=True)


class ActionFact(Fact):
    """A proposed action for logging / display purposes."""
    action_type = Field(str, mandatory=True)
    description = Field(str, mandatory=True)


class MoveCandidateFact(Fact):
    """A candidate move direction."""
    parent_id = Field(int, mandatory=True)
    direction = Field(str, mandatory=True)
    new_x = Field(int, mandatory=True)
    new_y = Field(int, mandatory=True)


class LoadCandidateFact(Fact):
    """A candidate load batch."""
    parent_id = Field(int, mandatory=True)
    batch = Field(dict, mandatory=True)


class ValidLoadFact(Fact):
    """A validated load batch."""
    parent_id = Field(int, mandatory=True)
    batch = Field(dict, mandatory=True)


class UnloadCandidateFact(Fact):
    """A candidate unload set of colors."""
    parent_id = Field(int, mandatory=True)
    pavilion_id = Field(str, mandatory=True)
    colors_to_unload = Field(tuple, mandatory=True)


class ValidUnloadFact(Fact):
    """A validated unload set of colors."""
    parent_id = Field(int, mandatory=True)
    pavilion_id = Field(str, mandatory=True)
    colors_to_unload = Field(tuple, mandatory=True)

