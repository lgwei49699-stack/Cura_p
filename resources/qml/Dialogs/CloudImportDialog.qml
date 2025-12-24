// 云端导入配置对话框

import QtQuick 2.10
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.3

import UM 1.5 as UM
import Cura 1.0 as Cura

UM.Dialog
{
    id: cloudImportDialog
    
    title: "云端导入"
    
    minimumWidth: 1000 * screenScaleFactor
    minimumHeight: 600 * screenScaleFactor
    width: minimumWidth
    height: minimumHeight
    
    property bool loading: false
    property var configList: []
    
    onVisibleChanged: {
        if (visible) {
            loading = true
            configList = []
            UM.ConfigUploadHandler.fetchCloudConfigs()
        }
    }
    
    Item
    {
        anchors.fill: parent
        
        // 监听配置列表获取成功
        Connections
        {
            target: UM.ConfigUploadHandler
            function onCloudConfigsFetched(configs)
            {
                console.log("收到配置列表:", JSON.stringify(configs))
                cloudImportDialog.loading = false
                cloudImportDialog.configList = configs
            }
            
            function onCloudConfigsFetchFailed(errorMessage)
            {
                console.log("获取配置列表失败:", errorMessage)
                cloudImportDialog.loading = false
            }
        }
        
        // 加载中提示
        UM.Label
        {
            anchors.centerIn: parent
            text: "加载中..."
            font: UM.Theme.getFont("default")
            visible: cloudImportDialog.loading
            z: 1
        }
        
        // 配置列表
        Column
        {
            anchors.fill: parent
            spacing: 0
            visible: !cloudImportDialog.loading
            
            // 表头
            Rectangle
            {
                width: parent.width
                height: 40 * screenScaleFactor
                color: UM.Theme.getColor("main_background")
                border.width: 1
                border.color: UM.Theme.getColor("lining")
                
                Row
                {
                    anchors.fill: parent
                    anchors.margins: 8 * screenScaleFactor
                    spacing: 10 * screenScaleFactor
                    
                    UM.Label
                    {
                        width: parent.width * 0.15
                        height: parent.height
                        text: "方案名称"
                        font: UM.Theme.getFont("default_bold")
                        verticalAlignment: Text.AlignVCenter
                    }
                    
                    UM.Label
                    {
                        width: parent.width * 0.35
                        height: parent.height
                        text: "方案文件"
                        font: UM.Theme.getFont("default_bold")
                        verticalAlignment: Text.AlignVCenter
                    }
                    
                    UM.Label
                    {
                        width: parent.width * 0.3
                        height: parent.height
                        text: "备注"
                        font: UM.Theme.getFont("default_bold")
                        verticalAlignment: Text.AlignVCenter
                    }
                    
                    UM.Label
                    {
                        width: parent.width * 0.15
                        height: parent.height
                        text: "操作"
                        font: UM.Theme.getFont("default_bold")
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
            
            // 列表内容
            ScrollView
            {
                width: parent.width
                height: parent.height - 40 * screenScaleFactor
                clip: true
                
                ListView
                {
                    id: configListView
                    model: cloudImportDialog.configList
                    spacing: 0
                    
                    delegate: Rectangle
                    {
                        width: configListView.width
                        height: Math.max(60 * screenScaleFactor, contentRow.implicitHeight + 16 * screenScaleFactor)
                        color: index % 2 === 0 ? UM.Theme.getColor("main_background") : UM.Theme.getColor("action_button_disabled")
                        border.width: 1
                        border.color: UM.Theme.getColor("lining")
                        
                        Row
                        {
                            id: contentRow
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 8 * screenScaleFactor
                            anchors.rightMargin: 8 * screenScaleFactor
                            spacing: 10 * screenScaleFactor
                            
                            // 方案名称
                            Item
                            {
                                width: parent.width * 0.15
                                height: nameLabel.height
                                
                                UM.Label
                                {
                                    id: nameLabel
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width
                                    text: modelData.name || ""
                                    font: UM.Theme.getFont("default")
                                    wrapMode: Text.Wrap
                                }
                            }
                            
                            // 方案文件（完整URL）
                            Item
                            {
                                width: parent.width * 0.35
                                height: fileUrlLabel.height
                                
                                UM.Label
                                {
                                    id: fileUrlLabel
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width
                                    text: modelData.configFileUrl || ""
                                    font: UM.Theme.getFont("default")
                                    wrapMode: Text.Wrap
                                }
                            }
                            
                            // 备注
                            Item
                            {
                                width: parent.width * 0.3
                                height: infoLabel.height
                                
                                UM.Label
                                {
                                    id: infoLabel
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width
                                    text: modelData.info || ""
                                    font: UM.Theme.getFont("default")
                                    wrapMode: Text.Wrap
                                }
                            }
                            
                            // 操作按钮（右对齐）
                            Item
                            {
                                width: parent.width * 0.15
                                height: actionButton.height
                                
                                Cura.SecondaryButton
                                {
                                    id: actionButton
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "设置此参数"
                                    onClicked: {
                                        console.log("导入配置:", modelData.name)
                                        UM.ConfigUploadHandler.importCloudConfig(
                                            modelData.configFileUrl,
                                            modelData.name
                                        )
                                        cloudImportDialog.accept()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        // 空状态提示
        UM.Label
        {
            anchors.centerIn: parent
            text: "暂无配置"
            font: UM.Theme.getFont("default")
            visible: !cloudImportDialog.loading && cloudImportDialog.configList.length === 0
            z: 1
        }
    }
    
    rightButtons: [
        Cura.TertiaryButton
        {
            text: "取消"
            onClicked: cloudImportDialog.reject()
        }
    ]
}
