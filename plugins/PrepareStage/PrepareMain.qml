//Copyright (c) 2021 Ultimaker B.V.
//Cura is released under the terms of the LGPLv3 or higher.

import QtQuick 2.4

import UM 1.0 as UM
import Cura 1.0 as Cura

Item
{
    id: prepareMain
    property string machineId: ""
    Cura.ActionPanelWidget
    {
        id: actionPanelWidget
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: UM.Theme.getSize("thick_margin").width
        anchors.bottomMargin: UM.Theme.getSize("thick_margin").height
        machineId: prepareMain.machineId
        function updateMachineId(id) {
            machineId = id;
        }
    }
    
    Connections 
    {
        target: Cura.MachineManager
        function onActiveMachineIdChanged(id)
        {
            console.log("Signal received with ID--:", id);
            prepareMain.machineId = id;
            actionPanelWidget.updateMachineId(id);
        }
    }   

    Component.onCompleted: {
        var initialId = PythonHandler.active_machine_id
        actionPanelWidget.updateMachineId(initialId);
        console.log("Initial machine ID:", initialId)
    } 
}