# Generated by Django 2.2.16 on 2020-10-19 22:03

import cjwstate.models.commands.util
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0017_nix_delta_sql_polymorphism"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="addtabcommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="addtabcommand",
            name="tab",
        ),
        migrations.RemoveField(
            model_name="changedataversioncommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="changedataversioncommand",
            name="step",
        ),
        migrations.RemoveField(
            model_name="changeparameterscommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="changeparameterscommand",
            name="step",
        ),
        migrations.RemoveField(
            model_name="changestepnotescommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="changestepnotescommand",
            name="step",
        ),
        migrations.RemoveField(
            model_name="changeworkflowtitlecommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="deletemodulecommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="deletemodulecommand",
            name="step",
        ),
        migrations.RemoveField(
            model_name="deletetabcommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="deletetabcommand",
            name="tab",
        ),
        migrations.RemoveField(
            model_name="duplicatetabcommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="duplicatetabcommand",
            name="tab",
        ),
        migrations.RemoveField(
            model_name="reordermodulescommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="reordermodulescommand",
            name="tab",
        ),
        migrations.RemoveField(
            model_name="reordertabscommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="settabnamecommand",
            name="delta_ptr",
        ),
        migrations.RemoveField(
            model_name="settabnamecommand",
            name="tab",
        ),
        migrations.DeleteModel(
            name="AddModuleCommand",
        ),
        migrations.DeleteModel(
            name="AddTabCommand",
        ),
        migrations.DeleteModel(
            name="ChangeDataVersionCommand",
        ),
        migrations.DeleteModel(
            name="ChangeParametersCommand",
        ),
        migrations.DeleteModel(
            name="ChangeStepNotesCommand",
        ),
        migrations.DeleteModel(
            name="ChangeWorkflowTitleCommand",
        ),
        migrations.DeleteModel(
            name="DeleteModuleCommand",
        ),
        migrations.DeleteModel(
            name="DeleteTabCommand",
        ),
        migrations.DeleteModel(
            name="DuplicateTabCommand",
        ),
        migrations.DeleteModel(
            name="ReorderModulesCommand",
        ),
        migrations.DeleteModel(
            name="ReorderTabsCommand",
        ),
        migrations.DeleteModel(
            name="SetTabNameCommand",
        ),
        migrations.CreateModel(
            name="AddModuleCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(cjwstate.models.commands.util.ChangesStepOutputs, "server.delta"),
        ),
        migrations.CreateModel(
            name="AddTabCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("server.delta",),
        ),
        migrations.CreateModel(
            name="ChangeDataVersionCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(cjwstate.models.commands.util.ChangesStepOutputs, "server.delta"),
        ),
        migrations.CreateModel(
            name="ChangeParametersCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(cjwstate.models.commands.util.ChangesStepOutputs, "server.delta"),
        ),
        migrations.CreateModel(
            name="ChangeStepNotesCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("server.delta",),
        ),
        migrations.CreateModel(
            name="ChangeWorkflowTitleCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("server.delta",),
        ),
        migrations.CreateModel(
            name="DeleteModuleCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(cjwstate.models.commands.util.ChangesStepOutputs, "server.delta"),
        ),
        migrations.CreateModel(
            name="DeleteTabCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("server.delta",),
        ),
        migrations.CreateModel(
            name="DuplicateTabCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("server.delta",),
        ),
        migrations.CreateModel(
            name="ReorderModulesCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(cjwstate.models.commands.util.ChangesStepOutputs, "server.delta"),
        ),
        migrations.CreateModel(
            name="ReorderTabsCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(cjwstate.models.commands.util.ChangesStepOutputs, "server.delta"),
        ),
        migrations.CreateModel(
            name="SetTabNameCommand",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(cjwstate.models.commands.util.ChangesStepOutputs, "server.delta"),
        ),
        migrations.RenameField(
            model_name="delta",
            old_name="migrate_step",
            new_name="step",
        ),
        migrations.RenameField(
            model_name="delta",
            old_name="migrate_step_delta_ids",
            new_name="step_delta_ids",
        ),
        migrations.RenameField(
            model_name="delta",
            old_name="migrate_tab",
            new_name="tab",
        ),
    ]
