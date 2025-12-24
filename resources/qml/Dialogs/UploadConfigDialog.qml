// Copyright (c) 2023 Wisebeginner
// 上传配置文件对话框

import QtQuick 2.10
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.3

import UM 1.5 as UM
import Cura 1.0 as Cura

UM.Dialog
{
    id: uploadConfigDialog
    
    title: "新增cure打印配置"
    
    minimumWidth: 400 * screenScaleFactor
    minimumHeight: 300 * screenScaleFactor
    width: minimumWidth
    height: minimumHeight
    
    property string configName: ""
    property string configRemarks: ""
    property bool uploading: false
    
    onAccepted: {
        if (configName.trim() !== "") {
            uploading = true
            UM.ConfigUploadHandler.uploadConfig(configName.trim(), configRemarks.trim())
        }
    }
    
    onVisibleChanged: {
        if (visible) {
            configName = ""
            configRemarks = ""
            uploading = false
        }
    }
    
    Item
    {
        anchors.fill: parent
        
        Column
        {
            width: parent.width
            spacing: UM.Theme.getSize("default_margin").height
            
            // 配置名称
            UM.Label
            {
                text: "配置名称"
                font: UM.Theme.getFont("default")
            }
            
            Cura.TextField
            {
                id: configNameField
                width: parent.width
                placeholderText: "0/20"
                maximumLength: 20
                selectByMouse: true
                text: uploadConfigDialog.configName
                onTextChanged: uploadConfigDialog.configName = text
            }
            
            // 备注
            UM.Label
            {
                text: "备注"
                font: UM.Theme.getFont("default")
            }
            
            ScrollView
            {
                width: parent.width
                height: 100
                
                TextArea
                {
                    id: remarksField
                    width: parent.width
                    selectByMouse: true
                    wrapMode: TextArea.Wrap
                    background: UM.UnderlineBackground {}
                    color: UM.Theme.getColor("text")
                    font: UM.Theme.getFont("default")
                    text: uploadConfigDialog.configRemarks
                    onTextChanged: uploadConfigDialog.configRemarks = text
                }
            }
        }
    }
    
    rightButtons: [
        Cura.TertiaryButton
        {
            text: "取消"
            onClicked: uploadConfigDialog.reject()
        },
        Cura.PrimaryButton
        {
            text: "确认"
            enabled: uploadConfigDialog.configName.trim().length > 0 && !uploadConfigDialog.uploading
            onClicked: uploadConfigDialog.accept()
        }
    ]
}
