# -*- coding: utf-8 -*-

class Selection(object):
    list = []
    folded = []
    default = None

    @classmethod
    def name(cls, state):
        states_dict = dict(cls.list)
        if state in states_dict:
            return states_dict[state]

    @classmethod
    def values(cls):
        return list(dict(cls.list))


class ApproverState(Selection):
    list = [
        ('to approve', 'To Approve'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    default = list[0][0]


class ApproverStateUpdated(Selection):
    list = [
        ('Draft', 'Draft'),
        ('Approved', 'Approved'),
        ('Approval Inprogress', 'Approval Inprogress'),
        ('Rejected', 'Rejected'),
    ]
    default = list[0][0]

class ApprovalMethods(Selection):
    list = [
        ('button', 'Button'),
    ]
    default = list[0][0]


class DocumentState(Selection):
    list = [
        ('draft', 'Draft'),
        ('inprogress', 'Inprogress'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]
    default = list[0][0]

class DocumentVisibility(Selection):
    list = [
        ('all_users', 'All Users'),
        ('followers', 'Followers'),
        ('approvers', 'Approvers'),
    ]
    default = list[0][0]

class ApprovalStep(Selection):
    step_range = list(range(1, 21))
    list = [("{:02d}".format(step), "{:02d}".format(step)) for step in step_range]
    default = list[0][0]
