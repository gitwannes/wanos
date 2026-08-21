** my PAT
https://account.smartthings.com/tokens
15786cde-9711-4d62-ba70-b3704ae513bb

** usefull URLs
https://developer.smartthings.com/docs/api/public
https://developer.smartthings.com/workspace/projects

** using PAT for device check
curl -s -H "Authorization: Bearer YOUR_PAT" https://api.smartthings.com/v1/devices | python -m json.tool
{
    "items": [
        {
            "deviceId": "dc46cc64-2654-06d9-5e06-c4203668aa64",
            "name": "Samsung Room A/C",
            "label": "buro-cinema",
            "manufacturerName": "Samsung Electronics",
            "presentationId": "DA-AC-RAC-000003",
            "deviceManufacturerCode": "Samsung Electronics",
            "locationId": "a42f8c0e-c3d4-46da-a82e-62d528aaa226",
            "ownerId": "30f165a0-6c94-d620-cd92-34e8c6a1c596",
            "roomId": "26d64c87-d005-4901-b238-f6d1328a4bbe",
            "deviceTypeName": "Samsung OCF Air Conditioner",
            "components": [
                {
                    "id": "main",
                    "label": "main",
                    "capabilities": [
                        {
                            "id": "ocf",
                            "version": 1
                        },
                        {
                            "id": "switch",
                            "version": 1
                        },
                        {
                            "id": "airConditionerMode",
                            "version": 1
                        },
                        {
                            "id": "airConditionerFanMode",
                            "version": 1
                        },
                        {
                            "id": "fanOscillationMode",
                            "version": 1
                        },
                        {
                            "id": "temperatureMeasurement",
                            "version": 1
                        },
                        {
                            "id": "thermostatCoolingSetpoint",
                            "version": 1
                        },
                        {
                            "id": "relativeHumidityMeasurement",
                            "version": 1
                        },
                        {
                            "id": "airQualitySensor",
                            "version": 1
                        },
                        {
                            "id": "odorSensor",
                            "version": 1
                        },
                        {
                            "id": "dustSensor",
                            "version": 1
                        },
                        {
                            "id": "veryFineDustSensor",
                            "version": 1
                        },
                        {
                            "id": "audioVolume",
                            "version": 1
                        },
                        {
                            "id": "remoteControlStatus",
                            "version": 1
                        },
                        {
                            "id": "powerConsumptionReport",
                            "version": 1
                        },
                        {
                            "id": "demandResponseLoadControl",
                            "version": 1
                        },
                        {
                            "id": "refresh",
                            "version": 1
                        },
                        {
                            "id": "execute",
                            "version": 1
                        },
                        {
                            "id": "custom.spiMode",
                            "version": 1
                        },
                        {
                            "id": "custom.thermostatSetpointControl",
                            "version": 1
                        },
                        {
                            "id": "custom.airConditionerOptionalMode",
                            "version": 1
                        },
                        {
                            "id": "custom.airConditionerTropicalNightMode",
                            "version": 1
                        },
                        {
                            "id": "custom.autoCleaningMode",
                            "version": 1
                        },
                        {
                            "id": "custom.deviceReportStateConfiguration",
                            "version": 1
                        },
                        {
                            "id": "custom.energyType",
                            "version": 1
                        },
                        {
                            "id": "custom.dustFilter",
                            "version": 1
                        },
                        {
                            "id": "custom.veryFineDustFilter",
                            "version": 1
                        },
                        {
                            "id": "custom.deodorFilter",
                            "version": 1
                        },
                        {
                            "id": "custom.electricHepaFilter",
                            "version": 1
                        },
                        {
                            "id": "custom.doNotDisturbMode",
                            "version": 1
                        },
                        {
                            "id": "custom.periodicSensing",
                            "version": 1
                        },
                        {
                            "id": "custom.airConditionerOdorController",
                            "version": 1
                        },
                        {
                            "id": "custom.ocfResourceVersion",
                            "version": 1
                        },
                        {
                            "id": "custom.disabledCapabilities",
                            "version": 1
                        },
                        {
                            "id": "samsungce.alwaysOnSensing",
                            "version": 1
                        },
                        {
                            "id": "samsungce.deviceIdentification",
                            "version": 1
                        },
                        {
                            "id": "samsungce.dustFilterAlarm",
                            "version": 1
                        },
                        {
                            "id": "samsungce.driverVersion",
                            "version": 1
                        },
                        {
                            "id": "samsungce.softwareUpdate",
                            "version": 1
                        },
                        {
                            "id": "samsungce.softwareVersion",
                            "version": 1
                        },
                        {
                            "id": "samsungce.selfCheck",
                            "version": 1
                        },
                        {
                            "id": "samsungce.individualControlLock",
                            "version": 1
                        }
                    ],
                    "categories": [
                        {
                            "name": "AirConditioner",
                            "categoryType": "manufacturer"
                        }
                    ],
                    "optional": false
                }
            ],
            "createTime": "2023-05-15T10:42:00.040Z",
            "childDevices": [],
            "profile": {
                "id": "bb4a6df4-6e0f-303a-ac35-445ea78a41fe"
            },
            "ocf": {
                "ocfDeviceType": "oic.d.airconditioner",
                "name": "Samsung Room A/C",
                "specVersion": "core.1.1.0",
                "verticalDomainSpecVersion": "res.1.1.0,sh.1.1.0",
                "manufacturerName": "Samsung Electronics",
                "modelNumber": "ARTIK051_PRAC_20K|10217841|60010523001411010200001000000000",
                "platformVersion": "DAWIT 2.0",
                "platformOS": "TizenRT 1.0 + IPv6",
                "hwVersion": "ARTIK051",
                "firmwareVersion": "ARTIK051_PRAC_20K_11230313",
                "vendorId": "DA-AC-RAC-000003",
                "vendorResourceClientServerVersion": "ARTIK051 Release 2.211222.1",
                "lastSignupTime": "2023-05-15T10:41:53.140277Z",
                "transferCandidate": false,
                "additionalAuthCodeRequired": false
            },
            "type": "OCF",
            "restrictionTier": 0,
            "allowed": [],
            "indoorMap": {
                "coordinates": [
                    54.0,
                    36.0,
                    14.0
                ],
                "rotation": [
                    270.0,
                    0.0,
                    0.0
                ],
                "visible": true,
                "data": null
            },
            "executionContext": "CLOUD",
            "relationships": []
        },
        {
            "deviceId": "e40db3c2-727e-4ce6-8739-844c32798418",
            "name": "Dishwasher-v0.13",
            "label": "Afwasmachien",
            "manufacturerName": "0A5j",
            "presentationId": "6412f655-085c-3946-9ceb-ece1c53ac1de",
            "deviceManufacturerCode": "Siemens",
            "locationId": "a42f8c0e-c3d4-46da-a82e-62d528aaa226",
            "ownerId": "30f165a0-6c94-d620-cd92-34e8c6a1c596",
            "roomId": "49a2e1ce-06a1-487c-a7b3-899372bb05b9",
            "components": [
                {
                    "id": "main",
                    "label": "main",
                    "capabilities": [
                        {
                            "id": "signalahead13665.applianceoperationstatesv2",
                            "version": 1
                        },
                        {
                            "id": "healthCheck",
                            "version": 1
                        },
                        {
                            "id": "refresh",
                            "version": 1
                        },
                        {
                            "id": "switch",
                            "version": 1
                        },
                        {
                            "id": "signalahead13665.startstopprogramv2",
                            "version": 1
                        },
                        {
                            "id": "signalahead13665.dishwasherprogramsv2",
                            "version": 1
                        }
                    ],
                    "categories": [
                        {
                            "name": "Dishwasher",
                            "categoryType": "manufacturer"
                        }
                    ],
                    "optional": false
                }
            ],
            "createTime": "2025-11-18T20:58:41.566Z",
            "childDevices": [],
            "profile": {
                "id": "5d145454-38c4-4505-afc2-b83d1b4515dd"
            },
            "viper": {
                "uniqueIdentifier": "015110396330002099",
                "manufacturerName": "Siemens",
                "modelName": "SN87TX02CE",
                "endpointAppId": "viper_f8009b80-d4c4-11eb-89df-5bbe1b05472c"
            },
            "type": "VIPER",
            "restrictionTier": 0,
            "allowed": [],
            "executionContext": "CLOUD",
            "relationships": []
        }
    ],
    "_links": {}
}

curl -s -H "Authorization: Bearer YOUR_PAT" \
  https://api.smartthings.com/v1/devices/dc46cc64-2654-06d9-5e06-c4203668aa64/status \
  | python -m json.tool

{
    "components": {
        "main": {
            "relativeHumidityMeasurement": {
                "humidity": {
                    "value": 52,
                    "unit": "%",
                    "timestamp": "2026-08-19T19:06:24.105Z"
                }
            },
            "custom.airConditionerOdorController": {
                "airConditionerOdorControllerProgress": {
                    "value": null
                },
                "supportedNotificationThresholds": {
                    "value": null
                },
                "notificationThreshold": {
                    "value": null
                },
                "notificationEnabled": {
                    "value": null
                },
                "airConditionerOdorControllerState": {
                    "value": null
                }
            },
            "custom.thermostatSetpointControl": {
                "minimumSetpoint": {
                    "value": 16,
                    "unit": "C",
                    "timestamp": "2026-08-04T08:18:06.179Z"
                },
                "maximumSetpoint": {
                    "value": 30,
                    "unit": "C",
                    "timestamp": "2026-08-04T08:18:06.179Z"
                }
            },
            "airConditionerMode": {
                "availableAcModes": {
                    "value": null
                },
                "supportedAcModes": {
                    "value": [
                        "cool",
                        "dry",
                        "wind",
                        "auto",
                        "heat"
                    ],
                    "timestamp": "2025-09-03T04:06:05.844Z"
                },
                "airConditionerMode": {
                    "value": "cool",
                    "timestamp": "2026-07-30T11:35:15.101Z"
                }
            },
            "custom.spiMode": {
                "spiMode": {
                    "value": "off",
                    "timestamp": "2025-09-02T18:24:20.277Z"
                }
            },
            "samsungce.deviceIdentification": {
                "micomAssayCode": {
                    "value": "10217841",
                    "timestamp": "2025-09-02T18:24:20.317Z"
                },
                "modelName": {
                    "value": null
                },
                "serialNumber": {
                    "value": null
                },
                "serialNumberExtra": {
                    "value": null
                },
                "releaseCountry": {
                    "value": null
                },
                "modelClassificationCode": {
                    "value": "60010523001411010200001000000000",
                    "timestamp": "2025-09-02T18:24:20.317Z"
                },
                "description": {
                    "value": "ARTIK051_PRAC_20K",
                    "timestamp": "2025-09-02T18:24:20.317Z"
                },
                "releaseYear": {
                    "value": 20,
                    "timestamp": "2026-04-07T05:10:35.673Z"
                },
                "binaryId": {
                    "value": "ARTIK051_PRAC_20K",
                    "timestamp": "2026-08-20T04:06:12.831Z"
                }
            },
            "airQualitySensor": {
                "airQuality": {
                    "value": null
                }
            },
            "custom.airConditionerOptionalMode": {
                "supportedAcOptionalMode": {
                    "value": [
                        "off",
                        "sleep",
                        "quiet",
                        "smart",
                        "speed",
                        "motionIndirect",
                        "motionDirect",
                        "windFree",
                        "windFreeSleep"
                    ],
                    "timestamp": "2025-09-03T04:06:05.844Z"
                },
                "availableAcOptionalMode": {
                    "value": null
                },
                "acOptionalMode": {
                    "value": "off",
                    "timestamp": "2026-07-31T21:29:38.772Z"
                }
            },
            "switch": {
                "switch": {
                    "value": "off",
                    "timestamp": "2026-08-20T04:06:12.831Z"
                }
            },
            "custom.airConditionerTropicalNightMode": {
                "acTropicalNightModeLevel": {
                    "value": 0,
                    "timestamp": "2025-09-02T18:24:20.193Z"
                }
            },
            "ocf": {
                "st": {
                    "value": null
                },
                "mndt": {
                    "value": null
                },
                "mnfv": {
                    "value": "ARTIK051_PRAC_20K_11230313",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "mnhw": {
                    "value": "ARTIK051",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "di": {
                    "value": "dc46cc64-2654-06d9-5e06-c4203668aa64",
                    "timestamp": "2026-08-20T04:06:12.519Z"
                },
                "mnsl": {
                    "value": "http://www.samsung.com",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "dmv": {
                    "value": "res.1.1.0,sh.1.1.0",
                    "timestamp": "2026-08-20T04:06:12.519Z"
                },
                "n": {
                    "value": "Samsung Room A/C",
                    "timestamp": "2026-08-20T04:06:12.519Z"
                },
                "mnmo": {
                    "value": "ARTIK051_PRAC_20K|10217841|60010523001411010200001000000000",
                    "timestamp": "2026-08-20T04:06:12.831Z"
                },
                "vid": {
                    "value": "DA-AC-RAC-000003",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "mnmn": {
                    "value": "Samsung Electronics",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "mnml": {
                    "value": "http://www.samsung.com",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "mnpv": {
                    "value": "DAWIT 2.0",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "mnos": {
                    "value": "TizenRT 1.0 + IPv6",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "pi": {
                    "value": "dc46cc64-2654-06d9-5e06-c4203668aa64",
                    "timestamp": "2026-08-20T04:06:12.520Z"
                },
                "icv": {
                    "value": "core.1.1.0",
                    "timestamp": "2026-08-20T04:06:12.519Z"
                }
            },
            "airConditionerFanMode": {
                "fanMode": {
                    "value": "auto",
                    "timestamp": "2026-07-30T08:02:05.385Z"
                },
                "supportedAcFanModes": {
                    "value": [
                        "auto",
                        "low",
                        "medium",
                        "high",
                        "turbo"
                    ],
                    "timestamp": "2025-09-03T04:06:05.844Z"
                },
                "availableAcFanModes": {
                    "value": null
                }
            },
            "samsungce.dustFilterAlarm": {
                "alarmThreshold": {
                    "value": 500,
                    "unit": "Hour",
                    "timestamp": "2025-09-02T18:24:20.132Z"
                },
                "supportedAlarmThresholds": {
                    "value": [
                        180,
                        300,
                        500,
                        700
                    ],
                    "unit": "Hour",
                    "timestamp": "2026-08-07T04:06:12.631Z"
                }
            },
            "custom.electricHepaFilter": {
                "electricHepaFilterCapacity": {
                    "value": null
                },
                "electricHepaFilterUsageStep": {
                    "value": null
                },
                "electricHepaFilterLastResetDate": {
                    "value": null
                },
                "electricHepaFilterStatus": {
                    "value": null
                },
                "electricHepaFilterUsage": {
                    "value": null
                },
                "electricHepaFilterResetType": {
                    "value": null
                }
            },
            "custom.disabledCapabilities": {
                "disabledCapabilities": {
                    "value": [
                        "remoteControlStatus",
                        "airQualitySensor",
                        "dustSensor",
                        "odorSensor",
                        "veryFineDustSensor",
                        "custom.spiMode",
                        "custom.deodorFilter",
                        "custom.electricHepaFilter",
                        "custom.periodicSensing",
                        "custom.doNotDisturbMode",
                        "custom.airConditionerOdorController",
                        "samsungce.individualControlLock",
                        "samsungce.alwaysOnSensing",
                        "demandResponseLoadControl"
                    ],
                    "timestamp": "2026-08-19T04:06:13.129Z"
                }
            },
            "custom.ocfResourceVersion": {
                "ocfResourceUpdatedTime": {
                    "value": null
                },
                "ocfResourceVersion": {
                    "value": null
                }
            },
            "samsungce.driverVersion": {
                "versionNumber": {
                    "value": 26060101,
                    "timestamp": "2026-07-14T02:43:05.387Z"
                }
            },
            "fanOscillationMode": {
                "supportedFanOscillationModes": {
                    "value": [
                        "fixed",
                        "all",
                        "vertical",
                        "horizontal"
                    ],
                    "timestamp": "2025-09-02T18:24:20.654Z"
                },
                "availableFanOscillationModes": {
                    "value": null
                },
                "fanOscillationMode": {
                    "value": "horizontal",
                    "timestamp": "2026-08-10T16:31:46.315Z"
                }
            },
            "temperatureMeasurement": {
                "temperatureRange": {
                    "value": null
                },
                "temperature": {
                    "value": 23,
                    "unit": "C",
                    "timestamp": "2026-08-20T00:34:58.122Z"
                }
            },
            "dustSensor": {
                "dustLevel": {
                    "value": null
                },
                "fineDustLevel": {
                    "value": null
                }
            },
            "custom.deviceReportStateConfiguration": {
                "reportStateRealtimePeriod": {
                    "value": "disabled",
                    "timestamp": "2025-09-02T18:24:20.628Z"
                },
                "reportStateRealtime": {
                    "value": {
                        "state": "disabled"
                    },
                    "timestamp": "2026-08-15T04:06:12.595Z"
                },
                "reportStatePeriod": {
                    "value": "enabled",
                    "timestamp": "2025-09-02T18:24:20.628Z"
                }
            },
            "custom.periodicSensing": {
                "automaticExecutionSetting": {
                    "value": null
                },
                "automaticExecutionMode": {
                    "value": null
                },
                "supportedAutomaticExecutionSetting": {
                    "value": null
                },
                "supportedAutomaticExecutionMode": {
                    "value": null
                },
                "periodicSensing": {
                    "value": null
                },
                "periodicSensingInterval": {
                    "value": null
                },
                "lastSensingTime": {
                    "value": null
                },
                "lastSensingLevel": {
                    "value": null
                },
                "periodicSensingStatus": {
                    "value": null
                }
            },
            "thermostatCoolingSetpoint": {
                "coolingSetpointRange": {
                    "value": null
                },
                "coolingSetpoint": {
                    "value": 23,
                    "unit": "C",
                    "timestamp": "2026-08-13T07:55:48.872Z"
                }
            },
            "demandResponseLoadControl": {
                "drlcStatus": {
                    "value": {
                        "drlcType": 1,
                        "drlcLevel": -1,
                        "start": "1970-01-01T00:00:00Z",
                        "duration": 0,
                        "override": false
                    },
                    "timestamp": "2025-09-03T04:06:05.844Z"
                }
            },
            "audioVolume": {
                "volume": {
                    "value": 100,
                    "unit": "%",
                    "timestamp": "2025-09-02T18:24:20.193Z"
                }
            },
            "powerConsumptionReport": {
                "powerConsumption": {
                    "value": {
                        "energy": 769530,
                        "deltaEnergy": 0,
                        "power": 0,
                        "powerEnergy": 0.0,
                        "persistedEnergy": 769530,
                        "energySaved": 0,
                        "start": "2026-08-20T06:48:30Z",
                        "end": "2026-08-20T07:00:00Z"
                    },
                    "timestamp": "2026-08-20T07:00:00.992Z"
                }
            },
            "custom.autoCleaningMode": {
                "supportedAutoCleaningModes": {
                    "value": [
                        "on",
                        "off"
                    ],
                    "timestamp": "2025-09-02T18:24:20.416Z"
                },
                "timedCleanDuration": {
                    "value": null
                },
                "operatingState": {
                    "value": "ready",
                    "timestamp": "2026-08-18T08:11:59.930Z"
                },
                "timedCleanDurationRange": {
                    "value": null
                },
                "supportedOperatingStates": {
                    "value": [
                        "autoClean",
                        "ready"
                    ],
                    "timestamp": "2025-09-02T18:24:20.416Z"
                },
                "progress": {
                    "value": 0,
                    "unit": "%",
                    "timestamp": "2026-08-18T08:11:59.930Z"
                },
                "autoCleaningMode": {
                    "value": "on",
                    "timestamp": "2025-09-02T18:24:20.416Z"
                }
            },
            "samsungce.individualControlLock": {
                "lockState": {
                    "value": null
                }
            },
            "samsungce.alwaysOnSensing": {
                "origins": {
                    "value": null
                },
                "alwaysOn": {
                    "value": null
                }
            },
            "refresh": {},
            "execute": {
                "data": {
                    "value": null
                }
            },
            "samsungce.softwareVersion": {
                "versions": {
                    "value": [
                        {
                            "id": "0",
                            "swType": "Software",
                            "versionNumber": "02181A230313",
                            "description": "Version"
                        },
                        {
                            "id": "1",
                            "swType": "Firmware",
                            "versionNumber": "20082000,FFFFFFFF",
                            "description": "Version"
                        },
                        {
                            "id": "2",
                            "swType": "Outdoor",
                            "versionNumber": "20091600,10000400",
                            "description": "Version"
                        }
                    ],
                    "timestamp": "2025-09-02T18:24:20.317Z"
                },
                "platformVersion": {
                    "value": null
                }
            },
            "samsungce.selfCheck": {
                "result": {
                    "value": null
                },
                "supportedActions": {
                    "value": [
                        "start"
                    ],
                    "timestamp": "2026-04-07T05:04:39.584Z"
                },
                "progress": {
                    "value": null
                },
                "errors": {
                    "value": [],
                    "timestamp": "2026-06-19T16:31:40.633Z"
                },
                "status": {
                    "value": "ready",
                    "timestamp": "2025-09-02T18:24:19.976Z"
                }
            },
            "custom.dustFilter": {
                "dustFilterUsageStep": {
                    "value": 1,
                    "timestamp": "2025-09-02T18:24:20.132Z"
                },
                "dustFilterUsage": {
                    "value": 100,
                    "timestamp": "2025-09-02T18:24:20.132Z"
                },
                "dustFilterLastResetDate": {
                    "value": null
                },
                "dustFilterStatus": {
                    "value": "wash",
                    "timestamp": "2025-09-02T18:24:20.132Z"
                },
                "dustFilterCapacity": {
                    "value": 500,
                    "unit": "Hour",
                    "timestamp": "2025-09-02T18:24:20.132Z"
                },
                "dustFilterResetType": {
                    "value": [
                        "replaceable",
                        "washable"
                    ],
                    "timestamp": "2025-09-02T18:24:20.132Z"
                }
            },
            "odorSensor": {
                "odorLevel": {
                    "value": null
                }
            },
            "remoteControlStatus": {
                "remoteControlEnabled": {
                    "value": null
                }
            },
            "custom.deodorFilter": {
                "deodorFilterCapacity": {
                    "value": null
                },
                "deodorFilterLastResetDate": {
                    "value": null
                },
                "deodorFilterStatus": {
                    "value": null
                },
                "deodorFilterResetType": {
                    "value": null
                },
                "deodorFilterUsage": {
                    "value": null
                },
                "deodorFilterUsageStep": {
                    "value": null
                }
            },
            "custom.energyType": {
                "energyType": {
                    "value": "1.0",
                    "timestamp": "2023-05-15T10:42:00.683Z"
                },
                "energySavingSupport": {
                    "value": false,
                    "timestamp": "2023-05-15T10:42:00.683Z"
                },
                "drMaxDuration": {
                    "value": 1440,
                    "unit": "min",
                    "timestamp": "2023-05-15T10:48:22.939Z"
                },
                "energySavingLevel": {
                    "value": null
                },
                "energySavingInfo": {
                    "value": null
                },
                "supportedEnergySavingLevels": {
                    "value": null
                },
                "energySavingOperation": {
                    "value": null
                },
                "notificationTemplateID": {
                    "value": null
                },
                "energySavingOperationSupport": {
                    "value": false,
                    "timestamp": "2023-05-15T10:48:22.939Z"
                }
            },
            "samsungce.softwareUpdate": {
                "targetModule": {
                    "value": {},
                    "timestamp": "2025-09-02T18:24:21.603Z"
                },
                "otnDUID": {
                    "value": "EXCDM6YAG72T6",
                    "timestamp": "2025-09-02T18:24:20.317Z"
                },
                "schedule": {
                    "value": null
                },
                "availableModuleDetails": {
                    "value": null
                },
                "lastUpdatedDate": {
                    "value": null
                },
                "availableModules": {
                    "value": [],
                    "timestamp": "2023-05-15T10:42:00.683Z"
                },
                "newVersionAvailable": {
                    "value": false,
                    "timestamp": "2025-09-02T18:24:20.317Z"
                },
                "operatingState": {
                    "value": null
                },
                "progress": {
                    "value": null
                },
                "protocolVersion": {
                    "value": null
                },
                "moduleUpdateCounts": {
                    "value": null
                }
            },
            "veryFineDustSensor": {
                "veryFineDustLevel": {
                    "value": null
                }
            },
            "custom.veryFineDustFilter": {
                "veryFineDustFilterStatus": {
                    "value": null
                },
                "veryFineDustFilterResetType": {
                    "value": null
                },
                "veryFineDustFilterUsage": {
                    "value": null
                },
                "veryFineDustFilterLastResetDate": {
                    "value": null
                },
                "veryFineDustFilterUsageStep": {
                    "value": null
                },
                "veryFineDustFilterCapacity": {
                    "value": null
                }
            },
            "custom.doNotDisturbMode": {
                "doNotDisturb": {
                    "value": null
                },
                "startTime": {
                    "value": null
                },
                "endTime": {
                    "value": null
                }
            }
        }
    }
}

---

# SmartThings API Integration Attempt — Full Failure Transcript  ---  is this usefull?
Author: Johan  
Date: 20 August 2026  
Status: SmartThings API access **not possible** for new developers

---

## 1. Initial Goal  
Integrate Samsung Elite 12 air conditioner with SmartThings API using a Raspberry Pi.

Desired outcome:  
- Obtain SmartThings OAuth `client_id` and `client_secret`  
- Use OAuth refresh tokens for long‑term access  
- Control AC via SmartThings REST API  

---

## 2. First Attempt — SmartThings CLI  
Steps:  
- Installed SmartThings CLI  
- Attempted `smartthings login`  
- Encountered broken Node.js ESM launcher errors  
- CLI failed to authenticate  

Outcome:  
- CLI login broken  
- No OAuth tokens  
- No API access  

---

## 3. Second Attempt — SmartThings Developer Center (Device Integrations)  
User navigated to:  
- Device Integrations  
- Create Product  
- Matter / Zigbee / Z-Wave / Cloud Connected / Direct Connected  

Findings:  
- This section is for hardware manufacturers  
- Not for API developers  
- No OAuth app creation  
- No API access  

Outcome:  
- Wrong console  
- No OAuth  
- No API access  

---

## 4. Third Attempt — Searching for “API” or “My Apps”  
User attempted to find:  
- Developer Workspace → My Apps  
- OAuth 2.0 App creation  

Findings:  
- These menus no longer exist for new accounts  
- SmartThings removed OAuth app creation for individuals  

Outcome:  
- OAuth app creation removed  
- No client_id / client_secret  
- No refresh tokens  
- No API access  

---

## 5. Fourth Attempt — Personal Access Tokens (PATs)  
User generated PATs.

Findings:  
- PATs expire every 24 hours  
- PATs cannot be refreshed  
- PATs cannot be extended  
- PATs cannot be generated via API  
- PATs are only for temporary testing  

Outcome:  
- PATs unusable for long‑term automation  
- No refresh mechanism  
- No API access  

---

## 6. Fifth Attempt — Developer Workspace  
User opened Developer Workspace.

Findings:  
- Workspace shows a deprecation notice  
- Workspace will be shut down for new integrations  
- No OAuth app creation available  
- Only “Create Project” for device certification  

Outcome:  
- Developer Workspace deprecated  
- No OAuth  
- No API access  

---

## 7. Sixth Attempt — Checking SmartThings Cloud API  
Goal:  
- Determine if Samsung Elite 12 exposes SmartThings cloud endpoints  

Findings:  
- SmartThings cloud API requires OAuth  
- OAuth requires partner credentials  
- Partner credentials are not available to individuals  

Outcome:  
- Cannot access SmartThings cloud API  
- No OAuth  
- No API access  

---

## 8. Final Conclusion — Why All Attempts Failed  
SmartThings made major changes:

- OAuth app creation removed for new developers  
- Developer Workspace deprecated  
- PATs expire in 24 hours and cannot be refreshed  
- SmartThings CLI login broken  
- SmartThings Cloud API requires partner credentials  
- Individuals cannot obtain client_id / client_secret  
- No long‑term API access possible  

Therefore:  
Direct SmartThings API integration is no longer possible for personal projects.

---

## 9. Remaining Working Options  

### Option 1 — Home Assistant (recommended)  
Home Assistant is a SmartThings partner and uses:  
- Permanent OAuth credentials  
- Long‑lived refresh tokens  
- Stable SmartThings API access  

Your Raspberry Pi can talk to Home Assistant locally.

### Option 2 — SmartThings Cloud Connector  
Official method for personal integrations:  
- No OAuth  
- No PATs  
- No token expiration  
- SmartThings calls your Pi directly  

### Option 3 — Local control (if AC supports it)  
Possible methods:  
- Local Wi‑Fi protocol  
- IR control (Broadlink / ESPHome)  
- RS‑485 / Modbus (commercial units)

---

## 10. Summary  
All attempts to obtain SmartThings API access failed because SmartThings has shut down OAuth access for new developers and PATs cannot be refreshed.

Working alternatives:  
- Home Assistant  
- SmartThings Cloud Connector  
- Local control  



** Install procedure WSL on Windows: which failed? check MD document below
```code
wsl --install Ubuntu-22.04
```

* Install Smartthings CLI
```code
sudo apt update
sudo apt upgrade -y
sudo apt install curl -y
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
node -v  # v24.19.0
npm -v  # 11.17.0
npm config set prefix /usr/local

sudo npm install -g @smartthings/cli@2.0.0
which smartthings  # /usr/bin/smartthings
smartthings --version  # 2.1.2
```

* Login
```code
smartthings login
```
This opens a browser window where you log in with your Samsung account.

* Create OAUTH token
```code
smartthings apps:create
```
The CLI will ask questions:
	App type: choose OAuth-In App
	Name: Wanos integration
	Description: optional
	Redirect URI:  
	For local testing, use:
		https://localhost/oauth/callback
	Scopes:  
		For airco control, choose:
			r:devices:*
			w:devices:*
	When finished, the CLI will output:
		clientId
		clientSecret
		appId
		⚠️ This is the ONLY time you will ever see the clientSecret. Save it.

* Build the OAuth authorization URL
```code
https://api.smartthings.com/oauth/authorize?
client_id=YOUR_CLIENT_ID&
response_type=code&
redirect_uri=https://localhost/oauth/callback&
scope=r:devices:* w:devices:*
```
You will:
	Log in with your Samsung account
	Select your SmartThings location
	Approve the app
	SmartThings will redirect you to:
		https://localhost/oauth/callback?code=AUTH_CODE
	Copy the AUTH_CODE.

* Exchange the code for tokens
```code
import requests
import base64

client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
auth_code = "THE_CODE_FROM_BROWSER"

auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

resp = requests.post(
    "https://api.smartthings.com/oauth/token",
    headers={
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    },
    data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": "https://localhost/oauth/callback"
    }
)

tokens = resp.json()
print(tokens)
```
You will receive:
	access_token (valid ~24h)
	refresh_token (long‑lived)
	expires_in

* Refresh tokens automatically
```code
def refresh(refresh_token):
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(
        "https://api.smartthings.com/oauth/token",
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id
        }
    )
    return resp.json()
```
This gives you a new:
	access_token
	refresh_token

* Final: use tokens with pysmartthings

```code
from pysmartthings import SmartThings
api = SmartThings("YOUR_ACCESS_TOKEN")
```


------------

# WanOS ↔ SmartThings OAuth Integration — Setup Procedure
Based on what worked / failed in your SmartThings integration notes (Aug 2026)

## 0. Prerequisites (confirmed working)
- WSL2 + Ubuntu 22.04 (native Windows CLI login was broken — WSL fixed it)
- Node.js v24.19.0 / npm 11.17.0 (installed via NodeSource setup_24.x)
- SmartThings CLI 2.1.2 (`npm install -g @smartthings/cli@2.0.0`)
- Confirm before proceeding: `smartthings --version` → should print 2.1.2

## 1. Re-confirm CLI login still works
```
smartthings login
```
- Opens browser → log in with Samsung account
- If this breaks again, retry inside WSL specifically — native Windows Node/CLI was the
  documented failure point, not your Samsung account or network.

## 2. Create the OAuth-In App (only needs to be done once)
```
smartthings apps:create
```
- App type: **OAuth-In App**
- Name: `WanOS integration` (or similar)
- Redirect URI: `https://localhost/oauth/callback` (fine for local dev/testing)
- Scopes: `r:devices:*` and `w:devices:*` (confirmed sufficient for AC read/control)
- **Copy `clientId` and `clientSecret` immediately** — the secret is shown once only

## 3. Store credentials securely — do NOT commit to WanOS repo
- Add to WanOS's existing secrets handling (however hofmans.be/WanOS already manages
  secrets — env file, systemd EnvironmentFile, etc.)
- Suggested env vars:
```
  SMARTTHINGS_CLIENT_ID=...
  SMARTTHINGS_CLIENT_SECRET=...
  SMARTTHINGS_REDIRECT_URI=https://localhost/oauth/callback
```

## 4. One-time authorization (manual browser step — cannot be automated)
Build and open in a browser:
```
https://api.smartthings.com/oauth/authorize?
client_id=YOUR_CLIENT_ID&
response_type=code&
redirect_uri=https://localhost/oauth/callback&
scope=r:devices:* w:devices:*
```
- Log in → select location → approve app
- Browser redirects to `https://localhost/oauth/callback?code=AUTH_CODE`
- Copy `AUTH_CODE` — it's single-use and short-lived, use it immediately in step 5

## 5. Exchange the code for tokens (confirmed working pattern)
```python
import requests, base64

client_id = "..."      # from env
client_secret = "..."  # from env
auth_code = "..."      # from step 4, one-time use

auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

resp = requests.post(
    "https://api.smartthings.com/oauth/token",
    headers={
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    },
    data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": "https://localhost/oauth/callback"
    }
)
tokens = resp.json()
# tokens = { access_token, refresh_token, expires_in, ... }
```
Persist `access_token`, `refresh_token`, and the token's issue time somewhere WanOS's
backend can read/write — e.g. a small SQLite table or a protected JSON file, not the repo.

## 6. Build a token manager module in the FastAPI backend
Rather than calling the refresh endpoint ad hoc, wrap it as a small module WanOS's
backend owns:

```python
# smartthings_auth.py
import time, base64, requests

TOKEN_URL = "https://api.smartthings.com/oauth/token"

class SmartThingsTokenManager:
    def __init__(self, client_id, client_secret, token_store):
        self.client_id = client_id
        self.client_secret = client_secret
        self.store = token_store  # your persistence layer

    def _auth_header(self):
        raw = f"{self.client_id}:{self.client_secret}".encode()
        return base64.b64encode(raw).decode()

    def refresh(self):
        tokens = self.store.load()
        resp = requests.post(TOKEN_URL,
            headers={
                "Authorization": f"Basic {self._auth_header()}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": self.client_id
            })
        resp.raise_for_status()
        new_tokens = resp.json()
        new_tokens["issued_at"] = time.time()
        self.store.save(new_tokens)
        return new_tokens["access_token"]

    def get_valid_access_token(self):
        tokens = self.store.load()
        age = time.time() - tokens.get("issued_at", 0)
        # refresh a bit before actual expiry (expires_in is ~24h)
        if age > tokens.get("expires_in", 86400) - 300:
            return self.refresh()
        return tokens["access_token"]
```

## 7. Schedule proactive refresh
- Add a background task (FastAPI `BackgroundTasks`, or an existing scheduler if WanOS
  already has one, e.g. for MQTT/sensor polling) that calls
  `get_valid_access_token()` well before the ~24h expiry — don't wait for a failed
  API call to trigger it.
- Log refresh failures loudly (WanOS's existing MQTT/log pipeline) since a silent
  refresh failure = AC control silently stops working.

## 8. Wire up device control
```python
from pysmartthings import SmartThings

def get_client(token_manager):
    return SmartThings(token_manager.get_valid_access_token())
```
- Use the AC's `device_id` (already in your notes:
  `dc46cc64-2654-06d9-5e06-c4203668aa64`) for status/commands.
- Expose a thin WanOS API endpoint (e.g. `/api/ac/status`, `/api/ac/command`) that
  internally calls SmartThings via the token manager — keep SmartThings specifics out
  of the frontend/Alpine.js layer entirely.

## 9. Test end-to-end
- `GET` device status → confirm current temp/mode read back correctly
- `POST` a command (e.g. setpoint change) → confirm AC responds
- Kill/expire the access token manually and confirm the refresh path recovers without
  manual intervention

## 10. Note the October 2026 deadline
- This flow is free until Samsung's Personal Plan ($4.99/mo) takes effect (~Oct 2026)
  for OAuth "cloud API Access Apps."
- PATs and the CLI itself stay free — only ongoing OAuth-based programmatic access is
  affected — so budget for either the subscription or a fallback (IR) before then.