/*
 * Copyright 2016 Mobicage NV
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * @@license_version:1.1@@
 */

var formId = {
    "type" : "string",
    "inputParams" :
    {
        "name" : "id",
        "label" : "Identifier",
        "required" : true,
        "showMsg" : false,
        "typeInvite" : "Enter id",
        "value" : ""
    }
};

var formMessage = {
    "type" : "text",
    "inputParams" :
    {
        "name" : "message",
        "label" : "Message",
        "showMsg" : false,
        "typeInvite" : "Enter message",
        "size" : 500,
        "cols" : 40,
        "rows" : 3,
        "value" : ""
    }
};

var formMessageGroup = {
    "type" : "group",
    "inputParams" : 
    {
        "name" : "message_settings_group",
        "legend" : "Message settings",
        "collapsible" : true,
        "collapsed" : true,
        "fields" : [
            {
                "type" : "select",
                "inputParams" : 
                {
                    "name" : "branding",
                    "label" : "Branding",
                    "selectValues" : branding_keys,
                    "selectOptions" : branding_names,
                    "value" : ""
                }
            }, {
                "type" : "hidden",
                "inputParams" : 
                {
                    "name" : "auto_lock",/*
                                             * "label" : "Auto lock", "rightLabel" : "* Expert mode only",
                                             */
                    "value" : true,
                    "className": "rogerthat-hidden"
                }
            }, {
                "type" : "boolean",
                "inputParams" : 
                {
                    "name" : "vibrate",
                    "label" : "Vibrate",
                    "rightLabel" : "",
                    "value" : false
                }
            }, {
                "type" : "select",
                "inputParams" : 
                {
                    "name" : "alert_type",
                    "label" : "Alert type",
                    "selectValues" : ["SILENT", "BEEP", "RING_5", "RING_15", "RING_30", "RING_60"],
                    "selectOptions" : ["silent", "beep", "ring 5 seconds", "ring 15 seconds", "ring 30 seconds", "ring 60 seconds"],
                    "value" : "SILENT"
                }
            }, {
                "type" : "select",
                "inputParams" : 
                {
                    "name" : "alert_interval",
                    "label" : "Alert interval",
                    "selectValues" : ["NONE", "INTERVAL_5", "INTERVAL_15", "INTERVAL_30", "INTERVAL_60", "INTERVAL_300", "INTERVAL_900", "INTERVAL_3600"],
                    "selectOptions" : ["[no interval]", "5 seconds", "15 seconds", "35 seconds", "1 minute", "5 minutes", "15 minutes", "1 hour"],
                    "value" : "NONE"
                }
            }
        ]
    }
};

var formTerminals = [
     {
         "name": "in", 
         "direction": [0,-1],
         "offsetPosition": 
         {
             "left": 175, 
             "top": -15
         }, 
         "ddConfig": 
         {
             "type": "input",
             "allowedTypes": ["output"]
         }
     }, {
         "name": "positive", 
         "direction": [0,1],
         "nMaxWires": 1,
         "offsetPosition": {
             "left": 86, 
             "bottom": -15
             }, 
         "ddConfig": {
             "type": "output",
             "allowedTypes": ["input"]
         }
     }, {
         "name": "negative", 
         "direction": [0,1], 
         "nMaxWires": 1,
         "offsetPosition": {
             "right": 86, 
             "bottom": -15
             }, 
         "ddConfig": {
             "type": "output",
             "allowedTypes": ["input"]
         }
     }
];

var formGroupFields = [
     {
         "type" : "string",
         "inputParams" : 
         {
             "name" : "positive_caption",
             "label" : "Green button label",
             "required" : true,
             "showMsg" : true,
             "typeInvite" : "Enter label",
             "value" : "Submit"
         }
     }, {
         "type" : "string",
         "inputParams" : 
         {
             "name" : "positive_confirmation",
             "label" : "Green button confirmation",
             "required" : false,
             "showMsg" : true,
             "typeInvite" : "Enter confirmation",
             "value" : ""
         }
     }, {
         "type" : "string",
         "inputParams" : 
         {
             "name" : "negative_caption",
             "label" : "Red button label",
             "required" : true,
             "showMsg" : true,
             "typeInvite" : "Enter label",
             "value" : "Cancel"
         }
     }, {
         "type" : "string",
         "inputParams" : 
         {
             "name" : "negative_confirmation",
             "label" : "Red button confirmation",
             "required" : false,
             "showMsg" : true,
             "typeInvite" : "Enter confirmation",
             "value" : ""
         }
     }
];

var textFormMaxCharsField = {
    "type" : "integer",
    "inputParams" : {
        "name" : "max_chars",
        "label" : "Max chars",
        "value" : 50,
        "negative" : false,
        "required" : true
    }
};

var textFormFields = [
    textFormMaxCharsField,
    {
        "type" : "string",
        "inputParams" : {
            "name" : "place_holder",
            "label" : "Placeholder",
            "required" : false,
            "showMsg" : false,
            "typeInvite" : "Enter placeholder",
            "value" : ""
        }
    }, {
        "type" : "string",
        "inputParams" : {
            "name" : "value",
            "label" : "Value",
            "required" : false,
            "showMsg" : false,
            "typeInvite" : "Enter initial value",
            "value" : ""
        }
    }
];

var textBlockFields = [
    textFormMaxCharsField,
    {
        "type" : "string", // "text",
        "inputParams" : {
            "name" : "place_holder",
            "label" : "Placeholder",
            "required" : false,
            "showMsg" : false,
            "typeInvite" : "Enter placeholder",
            "value" : "",
            "rows": 3,
            "cols" : 40,
        }
    }, {
        "type" : "string", // "text",
        "inputParams" : {
            "name" : "value",
            "label" : "Value",
            "required" : false,
            "showMsg" : false,
            "typeInvite" : "Enter initial value",
            "value" : "",
            "rows": 3,
            "cols" : 40,
        }
    }
];

var sliderFormFields = [
    {
        "type" : "float",
        "inputParams" : {
            "name" : "min",
            "label" : "Minimum value",
            "typeInvite" : "Enter minimum value",
            "negative" : true,
            "required" : true,
            "value" : null
        }
    }, {
        "type" : "float",
        "inputParams" : {
            "name" : "max",
            "label" : "Maximum value",
            "typeInvite" : "Enter maximum value",
            "negative" : true,
            "required" : true,
            "value" : null
        }
    }, {
        "type" : "integer",
        "inputParams" : {
            "name" : "step",
            "label" : "Step",
            "typeInvite" : "Enter step",
            "negative" : false,
            "required" : false
        }
    }, {
        "type" : "integer",
        "inputParams" : {
            "name" : "precision",
            "label" : "Precision",
            "typeInvite" : "Enter precision",
            "description" : "Amount of digits after comma",
            "negative" : false,
            "required" : false
        }
    }
];

var photoFormFields = [
    {
        "type" : "boolean",
        "inputParams" : 
        {
            "name" : "crop",
            "label" : "Crop",
            "rightLabel" : "",
            "value" : false
        }
    }, {
      "type" : "string",
      "inputParams" : {
          "name" : "ratio",
          "label" : "Ratio",
          "required" : false,
          "showMsg" : false,
          "typeInvite" : "Eg. 40x20, 200x200, ...",
          "description" : "Only relevant when crop is selected",
          "value" : ""
      }
  },  {
      "type" : "select",
      "inputParams" :
      {
          "name" : "quality",
          "label" : "Quality",
          "selectValues" : ["best", "user", "100000", "200000", "400000", "800000"],
          "selectOptions" : ["Best quality", "User defined","Max 100Kb", "Max 200Kb", "Max 400Kb", "Max 800Kb"],
          "value" : "best"
      }
  },  {
      "type" : "select",
      "inputParams" :
      {
          "name" : "source",
          "label" : "Source",
          "selectValues" : ["camera", "gallery", "gallery_camera"],
          "selectOptions" : ["Camera", "Gallery", "Gallery and camera"],
          "value" : "camera"
      }
}
];

var gpsLocationFields = [{
    "type" : "boolean",
    "inputParams" : 
    {
        "name" : "gps",
        "label" : "GPS required",
        "rightLabel" : "",
        "value" : false
    }
}];

var formSuggestionsGroup = {
    "type" : "group",
    "inputParams" : 
    {
        "name" : "suggestions_group",
        "legend" : "Suggestions",
        "collapsible" : true,
        "collapsed" : true,
        "fields" : 
        [{
            "type" : "list",
            "inputParams" : 
            {
                "name" : "suggestions_list",
                "listAddLabel" : "Add suggestion",  
                "elementType" : {
                    "type" : "group",
                    "inputParams" : 
                    {
                        "name" : "suggestion",
                        "legend" : "Suggestion",
                        "collapsible" : true,
                        "fields" : 
                        [
                            {
                                "type" : "string",
                                "inputParams" : {
                                    "name" : "value",
                                    "label" : "Value",
                                    "typeInvite" : "Enter suggestion",
                                    "required": true
                                }
                            }
                        ]
                    }
                },
                "value" : []
            }
        }]
    }
};

var formChoicesGroup = {
    "type" : "group",
    "inputParams" : 
    {
        "name" : "choices_group",
        "legend" : "Choices",
        "collapsible" : true,
        "collapsed" : true,
        "fields" : 
        [{
            "type" : "list",
            "inputParams" : 
            {
                "name" : "choices_list",
                "listAddLabel" : "Add choice",  
                "elementType" : {
                    "type" : "group",
                    "inputParams" : 
                    {
                        "name" : "choice",
                        "legend" : "Choice",
                        "collapsible" : true,
                        "fields" : 
                        [
                            {
                                "type" : "string",
                                "inputParams" : {
                                    "name" : "value",
                                    "label" : "Identifier",
                                    "typeInvite" : "Enter choice identifier",
                                    "description" : "Identifier used from source code",
                                    "required": true
                                }
                            }, {
                                "type" : "string",
                                "inputParams" : {
                                    "name" : "label",
                                    "label" : "Label",
                                    "typeInvite" : "Enter label",
                                    "required": true
                                }
                            }
                        ]
                    }
                },
                "value" : [{
                    "label" : "",
                    "value" : ""
                }, {
                    "label" : "",
                    "value" : ""
                }]
            }
        }]
    }
};

var formAttachmentsGroup = {
    "type" : "group",
    "inputParams" :
    {
        "name" : "attachments_group",
        "legend" : "Attachments",
        "collapsible" : true,
        "collapsed" : true,
        "fields" :
        [{
            "type" : "list",
            "inputParams" :
            {
                "name" : "attachments_list",
                "listAddLabel" : "Add attachment",
                "elementType" : {
                    "type" : "group",
                    "inputParams" :
                    {
                        "name" : "attachment",
                        "legend" : "Attachment",
                        "collapsible" : true,
                        "fields" :
                        [
                            {
                                "type" : "string",
                                "inputParams" : {
                                    "name" : "label",
                                    "label" : "Name",
                                    "typeInvite" : "Enter attachment name",
                                    "required": true
                                }
                            },
                            {
                                "type" : "string",
                                "inputParams" : {
                                    "name" : "value",
                                    "label" : "URL",
                                    "typeInvite" : "Enter attachment url",
                                    "description" : "Direct link to the attachment",
                                    "required": true
                                }
                            }
                        ]
                    }
                },
                "value" : []
            }
        }]
    }
};

var formResultsEmailGroup = {
        "type" : "group",
        "inputParams" : 
        {
            "name" : "emails_group",
            "legend" : "Other email addresses",
            "collapsible" : true,
            "collapsed" : true,
            "fields" : 
            [{
                "type" : "list",
                "inputParams" : 
                {
                    "name" : "emails_list",
                    "listAddLabel" : "Add email address",  
                    "elementType" : {
                        "type" : "group",
                        "inputParams" : 
                        {
                            "name" : "email",
                            "legend" : "Email",
                            "collapsible" : true,
                            "fields" : 
                            [{
                                    "type" : "string",
                                    "inputParams" : {
                                        "name" : "email",
                                        "label" : "Email",
                                        "typeInvite" : "Enter email-address",
                                        "required": true
                                    }
                                }
                            ]
                        }
                    },
                    "value" : []
                }
            }]
        }
    };

var formInitialChoicesGroup = {
    "type" : "group",
    "inputParams" :
    {
        "name" : "initial_choices_group",
        "legend" : "Initially selected choices",
        "collapsible" : true,
        "collapsed" : true,
        "fields" :
        [{
            "type" : "list",
            "inputParams" :
            {
                "name" : "initial_choices_list",
                "listAddLabel" : "Add initially selected choice",  
                "elementType" : {
                    "type" : "group",
                    "inputParams" : 
                    {
                        "name" : "value",
                        "legend" : "Choice",
                        "collapsible" : true,
                        "fields" :
                        [
                            {
                                "type" : "string",
                                "inputParams" : {
                                    "name" : "value",
                                    "label" : "Identifier",
                                    "typeInvite" : "Enter selected choice id",
                                    "description" : "Identifier of an initially selected choice",
                                    "required": true
                                }
                            }
                        ]
                    }
                },
                "value" : []
            }
        }]
    }
};

var advanced_order_category_item = {
    "type" : "group",
    "inputParams" : {
        "name" : "button",
        "legend" : "Item",
        "collapsible" : true,
        "fields" : [
            {
                "type" : "string",
                "inputParams" : {
                    "name" : "id",
                    "label" : "Identifier",
                    "description" : "Identifier of the item",
                    "value" : "",
                    "required": true
                }
            },
            {
                "type" : "string",
                "inputParams" : {
                    "name" : "name",
                    "label" : "Name",
                    "description" : "Name of the item",
                    "required" : true,
                    "value" : ""
                }
            },
            {
                "type" : "string",
                "inputParams" : {
                    "name" : "description",
                    "label" : "Description",
                    "description" : "Description of the item",
                    "required" : false,
                    "value" : ""
                }
            },
            {
                "type" : "integer",
                "inputParams" : {
                    "name" : "value",
                    "label" : "Default value",
                    "description" : "Default value of the item",
                    "required" : true,
                    "negative" : false,
                    "value" : 0
                }
            },
            {
                "type" : "string",
                "inputParams" : {
                    "name" : "unit",
                    "label" : "Unit",
                    "description" : "Unit of the item",
                    "required" : true,
                    "value" : ""
                }
            },
            {
                "type" : "integer",
                "inputParams" : {
                    "name" : "unitPrice",
                    "label" : "Unit price",
                    "description" : "Unit price of the item",
                    "required" : true,
                    "negative" : false,
                }
            },
            {
                "type" : "integer",
                "inputParams" : {
                    "name" : "step",
                    "label" : "Step",
                    "description" : "Step of the item",
                    "required" : true,
                    "negative" : false,
                    "value" : 1
                }
            },
            {
                "type" : "string",
                "inputParams" : {
                    "name" : "stepUnit",
                    "label" : "Step unit",
                    "description" : "Step unit of the item",
                    "required" : false,
                    "value" : ""
                }
            },
            {
                "type" : "integer",
                "inputParams" : {
                    "name" : "stepUnitConversion",
                    "label" : "Step unit converstion",
                    "description" : "Step unit to unit conversion of the item",
                    "required" : false,
                    "negative" : false,
                }
            },
            {
                "type" : "string",
                "inputParams" : {
                    "name" : "imageUrl",
                    "label" : "Image url",
                    "description" : "Image url of the item (16:9 ratio)",
                    "required" : false,
                    "value" : ""
                }
            },
        ],
        "value" : {
            "id" : "",
            "name" : ""
        }
    }
};

var mfLanguage = {
	
	// Set a unique name for the language
	languageName: "MessageFlow",

	// InputEx fields for pipes properties
	propertiesFields: [
		// default fields (the "name" field is required by the WiringEditor):
		{type: "string", inputParams: {name: "name", label: "Flow\u00a0name", typeInvite: "Enter name", size: 27 } },
		{type: "text", inputParams: {name: "description", label: "Flow\u00a0description", typeInvite: "Enter description", cols: 30, rows: 3} },
		{type: "boolean", inputParams: {rightLabel: "This flow is multi-language", name: "multilanguage" } },
		{type: "string", inputParams: {name: "test_account", label: "Test\u00a0user\u00a0(optional)", typeInvite: "Enter email", size: 27 } },
        {
            type: "select",
            inputParams: {
                name: "test_language",
                label: "Test\u00a0language\u00a0",
                selectValues: [null, "en", "es", "fr", "nl"],
                selectOptions: ["[default]", "English", "Espa\u00f1ol (Spanish)", "fran\u00e7ais (French)", "Nederlands (Dutch)"],
                value: "bloe"
            }
        },
        {
            type: "select",
            inputParams: {
                name: "global_branding",
                label: "Set\u00a0global\u00a0branding",
                selectValues: branding_keys,
                selectOptions: branding_names,
                value: ""
            }
        }
	],
	
	// Set layout properties
	layoutOptions: {
	 	units: [
	 	        { position: 'top', height: 28, body: 'top'},
	 	        { position: 'left', width: 320, resize: true, body: 'left', gutter: '5px', collapse: true, 
	 	        	collapseSize: 25, scroll: true, animate: true },
	        	{ position: 'center', body: 'center', gutter: '5px' }
	   ]
	},
	
	// List of node types definition
	modules: [
  	    {
	    	"name": "Start",
	    	"container": {
	    		"xtype": "WireIt.FormContainer",
	    		"fields": [],
		          "terminals": [
		                        {
		                        	"name": "out", 
		                        	"direction": [0,1], 
		                        	"nMaxWires": 1,
		                        	"offsetPosition": {
		                        		"left": 175, 
		                        		"bottom": -15
		                        		}, 
	                        		"ddConfig": {
	                        			"type": "output",
	                        			"allowedTypes": ["input"]
	                        		}
		                        }
		                        ]
	    	}
	    },
	    {
	    	"name": "End",
	    	"container": {
	    		"xtype": "WireIt.FormContainer",
	    		"fields": [
					{
						"type" : "string",
						"inputParams" : 
						{
							"name" : "id",
							"label" : "Identifier",
							"required" : true,
							"showMsg" : false,
							"typeInvite" : "Enter id",
							"value" : ""
						}
					},
					{
		                "type" : "boolean",
		                "inputParams" : 
		                {
		                    "name" : "waitForFollowUpMessage",
		                    "label" : "Wait for follow up message",
		                    "rightLabel" : "",
		                    "value" : false
		                }
		            }
	    		],
		          "terminals": [
		                        {
		                        	"name": "end", 
		                        	"direction": [0,-1], 
		                        	"offsetPosition": {
		                        		"left": 175, 
		                        		"top": -15
		                        		}, 
	                        		"ddConfig": {
	                        			"type": "input",
	                        			"allowedTypes": ["output"]
	                        		}
		                        }
		                        ]
	    	}
        },
	    {
	    	"name": "Message",
	    	"container": {
	    		"xtype":"MessageBoxContainer",
	    	    "resizable": false,
	    	}
	    },
        {
            "name": "Text line",
            "container": {
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },
        {
            "name": "Text block",
            "container": {
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },
        {
            "name": "Text autocomplete",
            "container":{
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },
        {
            "name": "Single select",
            "container": {
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },
        {
            "name": "Multi select",
            "container": {
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },
        {
            "name": "Date select",
            "container": {
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },
        {
            "name": "Single slider",
            "container": {
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },
        {
            "name": "Range slider",
            "container": {
                "xtype": "JavascriptValidationFormWidgetContainer",
                "resizable": false
            }
        },{
            "name": "Photo upload",
            "container": {
                "xtype": "FormWidgetContainer",
                "title": "Photo upload form",
                "terminals": formTerminals,
                "fields": [
                    formId,
                    formMessage,
                    formMessageGroup,
                    {
                        "type" : "group",
                        "inputParams" : 
                        {
                            "name" : "form_settings_group",
                            "legend" : "Form settings",
                            "collapsible" : true,
                            "collapsed" : true,
                            "fields" : formGroupFields.concat(photoFormFields)
                        }
                    },
                    formAttachmentsGroup,
                ],
            }
        },{
            "name": "GPS Location",
            "container": {
                "xtype": "FormWidgetContainer",
                "title": "GPS location form",
                "terminals": formTerminals,
                "fields": [
                    formId,
                    formMessage,
                    formMessageGroup,
                    {
                        "type" : "group",
                        "inputParams" :
                        {
                            "name" : "form_settings_group",
                            "legend" : "Form settings",
                            "collapsible" : true,
                            "collapsed" : true,
                            "fields" : formGroupFields.concat(gpsLocationFields)
                        }
                    },
                    formAttachmentsGroup,
                ],
            }
        }, {
            "name" : "MYDIGIPASS",
            "container" : {
                "xtype" : "FormWidgetContainer",
                "title" : "MYDIGIPASS authentication form",
                "terminals" : formTerminals,
                "fields" : [ formId, formMessage, formMessageGroup, {
                    "type" : "group",
                    "inputParams" : {
                        "name" : "form_settings_group",
                        "legend" : "Form settings",
                        "collapsible" : true,
                        "collapsed" : true,
                        "fields" : formGroupFields
                    }
                }, {
                    "type" : "group",
                    "inputParams" : {
                        "name" : "mdp_scopes_group",
                        "legend" : "Scope",
                        "collapsible" : true,
                        "collapsed" : true,
                        "fields" : [ {
                            "type" : "boolean",
                            "inputParams" : {
                                "name" : "eid_profile",
                                "label" : "eid_profile",
                                "rightLabel" : "",
                                "value" : true
                            }
                        }, {
                            "type" : "boolean",
                            "inputParams" : {
                                "name" : "eid_address",
                                "label" : "eid_address",
                                "rightLabel" : "",
                                "value" : false
                            }
                        }, {
                            "type" : "boolean",
                            "inputParams" : {
                                "name" : "eid_photo",
                                "label" : "eid_photo",
                                "rightLabel" : "",
                                "value" : false
                            }
                        }, {
                            "type" : "boolean",
                            "inputParams" : {
                                "name" : "email",
                                "label" : "email",
                                "rightLabel" : "",
                                "value" : false
                            }
                        }, {
                            "type" : "boolean",
                            "inputParams" : {
                                "name" : "phone",
                                "label" : "phone",
                                "rightLabel" : "",
                                "value" : false
                            }
                        }, {
                            "type" : "boolean",
                            "inputParams" : {
                                "name" : "profile",
                                "label" : "profile",
                                "rightLabel" : "",
                                "value" : false
                            }
                        }, {
                            "type" : "boolean",
                            "inputParams" : {
                                "name" : "address",
                                "label" : "address",
                                "rightLabel" : "",
                                "value" : false
                            }
                        } ]
                    }
                }, formAttachmentsGroup ],
            }
        }, {
            "name": "Advanced order",
            "container": {
                "xtype": "FormWidgetContainer",
                "title": "Advanced order form",
                "terminals": formTerminals,
                "fields": [
                    formId,
                    formMessage,
                    formMessageGroup,
                    {
                        "type" : "group",
                        "inputParams" :
                        {
                            "name" : "form_settings_group",
                            "legend" : "Form settings",
                            "collapsible" : true,
                            "collapsed" : true,
                            "fields" : formGroupFields.concat([ {
                                "type" : "string",
                                "inputParams" : 
                                {
                                    "name" : "currency",
                                    "label" : "Currency",
                                    "required" : true,
                                    "value" : "€"
                                }
                            }])
                        }
                    },
                    {
                        "type" : "group",
                        "inputParams" : {
                            "name" : "advanced_order_group",
                            "legend" : "Categories",
                            "collapsible" : true,
                            "collapsed" : true,
                            "fields" : [
                                {
                                    "type" : "list",
                                    "inputParams" : 
                                    {
                                        "name" : "category_list",
                                        "listAddLabel" : "Add category",  
                                        "elementType" : {
                                            "type" : "group",
                                            "inputParams" : {
                                                "name" : "advanced_order_category",
                                                "legend" : "Category",
                                                "collapsible" : true,
                                                "collapsed" : true,
                                                "fields" : [
                                                    {
                                                        "type" : "string",
                                                        "inputParams" : {
                                                            "name" : "id",
                                                            "label" : "Identifier",
                                                            "description" : "Identifier of the category",
                                                            "value" : "",
                                                            "required": true
                                                        }
                                                    },
                                                    {
                                                        "type" : "string",
                                                        "inputParams" : {
                                                            "name" : "name",
                                                            "label" : "Name",
                                                            "description" : "Name of the category",
                                                            "required" : true,
                                                            "value" : ""
                                                        }
                                                    },
                                                    {
                                                        "type" : "list",
                                                        "inputParams" : 
                                                        {
                                                            "name" : "category_item_list",
                                                            "listAddLabel" : "Add item",  
                                                            "elementType" : advanced_order_category_item,
                                                            "value" : []
                                                        }
                                                    }
                                                ],
                                                "value" : {
                                                    "id" : "",
                                                    "name" : "",
                                                    "advanced_order_item_group" : []
                                                }
                                            }
                                        },
                                        "value" : []
                                    }
                                }

                            ],
                            "value" : {
                                "category_list" : []
                            }
                        }
                    },
                    formAttachmentsGroup,
                ],
            }
        }, {
            "name": "Message flow",
            "container": {
                "xtype": "SubMessageFlowContainer",
                "title": "Sub message flow",
                "terminals": [
                    {
                        "name": "in",
                        "direction": [0,-1],
                        "offsetPosition": {
                            "left": 175,
                            "top": -15
                        },
                        "ddConfig": {
                            "type": "input",
                            "allowedTypes": ["output"]
                        }
                    }
                ],
            }
        },
        {
	    	"name": "Results flush",
	    	"container": {
	    		"xtype": "WireIt.FormContainer",
	    		"fields": [					
		    		{
						"type" : "string",
						"inputParams" : 
						{
							"name" : "id",
							"label" : "Identifier",
							"required" : true,
							"showMsg" : false,
							"typeInvite" : "Enter id",
							"value" : ""
						}
					}
	    		],
                "terminals": [
                    {
                        "name": "in",
                        "direction": [0,-1],
                        "offsetPosition": {
                            "left": 175,
                            "top": -15
                        },
                        "ddConfig": {
                            "type": "input",
                            "allowedTypes": ["output"]
                        }
                    },
                    {
                    	"name": "out", 
                    	"direction": [0,1], 
                    	"nMaxWires": 1,
                    	"offsetPosition": {
                    		"left": 175, 
                    		"bottom": -15
                    		}, 
                		"ddConfig": {
                			"type": "output",
                			"allowedTypes": ["input"]
                		}
                    }
                ],
            }
        },        
        {
            "name": "Results email",
            "container": {
                "xtype": "WireIt.FormContainer",
                "fields": [
                    {
                        "type" : "string",
                        "inputParams" : 
                        {
                            "name" : "id",
                            "label" : "Identifier",
                            "required" : true,
                            "showMsg" : false,
                            "typeInvite" : "Enter id",
                            "value" : ""
                        }
                    },
                    {
                        "type" : "boolean",
                        "inputParams" : 
                        {
                            "name" : "emailadmins",
                            "label" : "Email admins",
                            "rightLabel" : "",
                            "description" : "Send email to all admin users",
                            "value" : true
                        }
                    },
                    formResultsEmailGroup
                ],
                "terminals": [
                    {
                        "name": "in",
                        "direction": [0,-1],
                        "offsetPosition": {
                            "left": 175,
                            "top": -15
                        },
                        "ddConfig": {
                            "type": "input",
                            "allowedTypes": ["output"]
                        }
                    },
                    {
                        "name": "out", 
                        "direction": [0,1], 
                        "nMaxWires": 1,
                        "offsetPosition": {
                            "left": 175, 
                            "bottom": -15
                            }, 
                        "ddConfig": {
                            "type": "output",
                            "allowedTypes": ["input"]
                        }
                    }
                ],
            }
        },
        {
            "name": "Flow code",
            "container": {
                "xtype":"FlowCodeContainer",
                "resizable": false
            }
        }
	]
};
var DEFAULT_JS_VALIDATION_CODE = "var run = function(result){\n    /* do some calculations */\n    /* return true or an error message */\n    /* return \"Error occurred\"; */\n    return true;\n};";

var MessageBoxContainer = function(options, layer) {
	MessageBoxContainer.superclass.constructor.call(this, options, layer);
	this.button_terminals = [];
	this.buildTextArea(options || {});
	   
	this.createTerminals();
};


YAHOO.extend(MessageBoxContainer, WireIt.Container, {
	   
	/**
     * Create the textarea for the javascript code
     * 
     * @method buildTextArea
     * @param {String}
     *            codeText
     */
	buildTextArea: function(config) {
		
		var formDef = {
			"parentEl": this.bodyEl,
			"name" : "",
			"legend" : "",
			"collapsible" : false,
			"collapsed" : false,
			"fields" : 
			[
				{
					"type" : "string",
					"inputParams" : 
					{
						"name" : "id",
						"label" : "Identifier",
						"required" : true,
						"showMsg" : false,
						"typeInvite" : "Enter id",
						"value" : ""
					}
				},
				{
					"type" : "text",
					"inputParams" : 
					{
						"name" : "message",
						"label" : "Message",
						"showMsg" : false,
						"typeInvite" : "Enter message",
						"size" : 500,
						"cols" : 40,
						"rows" : 3,
						"value" : ""
					}
				},
				{
					"type" : "group",
					"inputParams" : 
					{
						"name" : "settings_group",
						"legend" : "Message settings",
						"collapsible" : true,
						"collapsed" : true,
						"fields" : [
							{
								"type" : "select",
								"inputParams" : 
								{
									"name" : "branding",
									"label" : "Branding",
									"selectValues" : branding_keys,
									"selectOptions" : branding_names,
									"value" : ""
								}
							},
							{
								"type" : "hidden",
								"inputParams" : 
								{
									"name" : "auto_lock", /*
                                                             * "label" : "Auto lock", "rightLabel" : "* Expert mode
                                                             * only",
                                                             */
									"value" : true,
									"className": "rogerthat-hidden"
								}
							},
							{
								"type" : "boolean",
								"inputParams" : 
								{
									"name" : "rogerthat_button",
									"label" : "Rogerthat button",
									"rightLabel" : "",
									"value" : false
								}
							},
							{
								"type" : "boolean",
								"inputParams" : 
								{
									"name" : "vibrate",
									"label" : "Vibrate",
									"rightLabel" : "",
									"value" : false
								}
							},
							{
								"type" : "select",
								"inputParams" : 
								{
									"name" : "alert_type",
									"label" : "Alert type",
									"selectValues" : ["SILENT", "BEEP", "RING_5", "RING_15", "RING_30", "RING_60"],
									"selectOptions" : ["silent", "beep", "ring 5 seconds", "ring 15 seconds", "ring 30 seconds", "ring 60 seconds"],
									"value" : "SILENT"
								}
							},
							{
								"type" : "select",
								"inputParams" : 
								{
									"name" : "alert_interval",
									"label" : "Alert interval",
									"selectValues" : ["NONE", "INTERVAL_5", "INTERVAL_15", "INTERVAL_30", "INTERVAL_60", "INTERVAL_300", "INTERVAL_900", "INTERVAL_3600"],
									"selectOptions" : ["[no interval]", "5 seconds", "15 seconds", "35 seconds", "1 minute", "5 minutes", "15 minutes", "1 hour"],
									"value" : "NONE"
								}
							},
						]
					}
				},
				formAttachmentsGroup,
				{
					"type" : "group",
					"inputParams" : 
					{
						"name" : "buttons_group",
						"legend" : "Buttons",
						"collapsible" : true,
						"collapsed" : true,
						"fields" : 
						[
							{
								"type" : "list",
								"inputParams" : 
								{
									"name" : "buttons_list",
									"listAddLabel" : "Add button",	
									"elementType" : {
										"type" : "group",
										"inputParams" : {
											"name" : "button",
											"legend" : "Button",
											"collapsible" : true,
											"fields" : [
                                                {
                                                    "type" : "string",
                                                    "inputParams" : {
                                                        "name" : "id",
                                                        "label" : "Identifier",
                                                        "description" : "Identifier used from source code",
                                                        "value" : "",
                                                        "required": true
                                                    }
                                                },
												{
													"type" : "string",
													"inputParams" : {
														"name" : "caption",
														"label" : "Label",
														"description" : "Label of the button",
														"required" : true,
														"showMsg" : false,
														"minLength" : 1,
														"value" : ""
													}
												},
												{
													"type" : "string",
													"inputParams" : {
														"name" : "action",
														"label" : "Action",
														"description" : "http:// or https:// or tel:// or geo:// or confirm:// or mailto://",
														"value" : ""
													}
												}
											],
											"value" : {
												"caption" : "",
												"action" : "",
												"id" : ""
											}
										}
									},
									"value" : [
							
									]
								}
							}

						],
						"value" : {
							"buttons_list" : [

							]
						}
					}
				}
			]
		};
		var thizz = this;
		this.form = new YAHOO.inputEx.Group(formDef);
		this.form.onCollapseChanged = function() { thizz.positionTerminals() };
		this.message = this.form.getFieldByName('message');
		this.settings_group = this.form.getFieldByName('settings_group');
		this.settings_group.onCollapseChanged = function() { thizz.positionTerminals() };
		this.branding = this.settings_group.getFieldByName('branding');
		this.auto_lock = this.settings_group.getFieldByName('auto_lock');
		this.rogerthat_button = this.settings_group.getFieldByName('rogerthat_button');
		this.buttons_group = this.form.getFieldByName('buttons_group');
		this.buttons_group.onCollapseChanged = function() { thizz.positionTerminals() };
		this.button_list = this.buttons_group.getFieldByName('buttons_list');
		this.button_list.updatedEvt.subscribe(function (event) {thizz.createTerminals(event);});
		this.rogerthat_button.updatedEvt.subscribe(function (event) {thizz.createTerminals(event);});
		if (config.messageDef)
			this.form.setValue(config.messageDef);
	},
	   
	/**
     * Create (and re-create) the terminals with this.nParams input terminals
     * 
     * @method createTerminals
     */
	createTerminals: function(event) {
		
		// Input terminal
		if( !this.inputTerminal ) {
			this.inputTerminal = this.addTerminal({xtype: "WireIt.util.TerminalInput", name: "in", nMaxWires: Infinity});  
			this.inputTerminal.MessageBox = this;
		}
		
		// Rogerthat terminal
		if (this.rogerthat_button.getValue()) {
			if ( ! this.rogerthatTerminal) {
				this.rogerthatTerminal = this.addTerminal({xtype: "WireIt.util.TerminalOutput", name: "roger that", direction: [1,0], nMaxWires: 1});    
				$(this.rogerthatTerminal.el).append($('<div></div>').addClass('message_terminal_label').text("Roger that!")).removeAttr('title');
				WireIt.sn(this.rogerthatTerminal.el, null, {position: "absolute", right: "-15px", bottom: "30px"});
				this.rogerthatTerminal.MessageBox = this;
			}
		} else {
			if ( this.rogerthatTerminal) {
				this.rogerthatTerminal.remove()
				this.terminals[this.terminals.indexOf(this.rogerthatTerminal)] = null;
				this.terminals = WireIt.compact(this.terminals);
				this.rogerthatTerminal = null;
			}
		}
		      
		// Button terminals :
		var new_terminal_list = [];
		var thizz = this;
		$.each(this.button_list.subFields, function (i, button) {
			if ( ! button.term ) {
				var caption_field = button.getFieldByName('caption');
				var id_field = button.getFieldByName('id');
		        var term = thizz.addTerminal({xtype: "WireIt.util.TerminalOutput", "name": caption_field.getValue() || "button", nMaxWires: 1});
		        var label = $('<div></div>').addClass('message_terminal_label').text(id_field.getValue());
		        $(term.el).append(label).removeAttr('title');
		        WireIt.sn(term.el, null, {position: "absolute", bottom: "-15px"});
		        button.term = term;
		        id_field.updatedEvt.subscribe(function (event) {
		        	label.text(id_field.getValue());
		        });
		        caption_field.updatedEvt.subscribe(function (event) {
		        	term.options.name = caption_field.getValue();
		        });
			}
			new_terminal_list.push(button.term);
			button.onCollapseChanged = function () { thizz.positionTerminals() };
		});
		$.each(this.button_terminals, function(i, terminal) {
			if (new_terminal_list.indexOf(terminal) == -1) {
				terminal.remove();
			}
		});
		this.button_terminals = new_terminal_list;
		this.terminals = $.merge([], new_terminal_list);
		this.terminals.push(this.inputTerminal);
		if (this.rogerthatTerminal)
			this.terminals.push(this.rogerthatTerminal)
		
		this.positionTerminals();
	    // Declare the new terminals to the drag'n drop handler (so the wires are moved around with the container)
		this.dd.setTerminals(this.terminals);
	},

	/**
     * Reposition the terminals
     * 
     * @method positionTerminals
     */
	positionTerminals: function() {
        var width = WireIt.getIntStyle(this.el, "width");
        var height = WireIt.getIntStyle(this.el, "height");

        var outputsInterval = Math.floor(width/(this.button_terminals.length+1));
        
        $.each(this.button_terminals, function (i, terminal) {
	        YAHOO.util.Dom.setStyle(terminal.el, "left", (outputsInterval*(i+1))-15+"px" );
	        $.each(terminal.wires, function (j, wire) {
	        	wire.redraw();
	        });
        });
	      
	    // Input terminal
	    WireIt.sn(this.inputTerminal.el, null, {position: "absolute", top: "-15px", left: (Math.floor(width/2)-15)+"px"});
        $.each(this.inputTerminal.wires, function (j, wire) {
        	wire.redraw();
        });

        // Rogerthat terminal
        if (this.rogerthatTerminal) {
    	    WireIt.sn(this.rogerthatTerminal.el, null, {position: "absolute", right: "-15px", top: (Math.floor(height/2)-15)+"px"});
            $.each(this.rogerthatTerminal.wires, function (j, wire) {
            	wire.redraw();
            });
        }
	},
	   
	/**
     * Extend the getConfig to add the "codeText" property
     * 
     * @method getConfig
     */
	getConfig: function() {
	    var obj = MessageBoxContainer.superclass.getConfig.call(this);
		obj.messageDef = this.form.getValue();
	    return obj;
	}
	   
});

var CodeBoxContainer = function(options, layer) {
	CodeBoxContainer.superclass.constructor.call(this, options, layer);
	this.outlet_terminals = [];
	this.buildTextArea(options || {});
	   
	this.createTerminals();
};

YAHOO.extend(CodeBoxContainer, WireIt.Container, {
	   
	/**
     * Create the textarea for the javascript code
     * 
     * @method buildTextArea
     * @param {String}
     *            codeText
     */
	buildTextArea: function(config) {
		var formDef = {
			"parentEl": this.bodyEl,
			"name" : "",
			"legend" : "",
			"collapsible" : false,
			"collapsed" : false,
			"fields" : 
			[
				{
					"type" : "string",
					"inputParams" : 
					{
						"name" : "id",
						"label" : "Identifier",
						"required" : true,
						"showMsg" : false,
						"typeInvite" : "Enter id",
						"value" : ""
					}
				},
				{
					"type" : "select",
					"inputParams" : 
					{
						"name" : "programming_language",
						"label" : "Scripting language",
						"selectValues" : ["JYTHON", "JRUBY"],
						"selectOptions" : ["Jython", "JRuby"],
						"value" : "JYTHON"
					}
				},
				{
					"type" : "group",
					"inputParams" : 
					{
						"name" : "source_group",
						"legend" : "Source code",
						"collapsible" : true,
						"collapsed" : true,
						"fields" : [
							{
								"type" : "text",
								"inputParams" : 
								{
									"name" : "source",
									"required" : true,
									"showMsg" : false,
									"typeInvite" : "",
									"cols" : 60,
									"rows" : 15,
								}
							}
						]
					}
				},
				{
					"type" : "group",
					"inputParams" : 
					{
						"name" : "outlets_group",
						"legend" : "Outlets",
						"collapsible" : true,
						"collapsed" : true,
						"fields" : 
						[
							{
								"type" : "list",
								"inputParams" : 
								{
									"name" : "outlets_list",
									"listAddLabel" : "Add outlet",	
									"elementType" : {
										"type" : "string",
										"inputParams" : {
											"name" : "name",
											"label" : "Name",
											"required" : true,
											"showMsg" : false,
											"minLength" : 1,
											"value" : ""
										}
									},
									"value" : ["default"]
								}
							}

						],
						"value" : {
							"outlets_list" : ["default"]
						}
					}
				}
			]
		};
		var thizz = this;
		this.form = new YAHOO.inputEx.Group(formDef);
		this.source_group = this.form.getFieldByName('source_group');
		this.source = this.source_group.getFieldByName('source');
		this.outlets_group = this.form.getFieldByName('outlets_group');
		this.outlets_group.onCollapseChanged = function() { thizz.positionTerminals(); };
		this.outlets_list = this.outlets_group.getFieldByName('outlets_list');
		this.outlets_list.updatedEvt.subscribe(function (event) {thizz.createTerminals(event);});
		if (config.sourceDef) {
			this.form.setValue(config.sourceDef);
		} else {
			this.source.setValue("def run(previous_steps, state):\n    # do some calculations\n    # return name of next step\n    return \"default\"");
		}
		this.editor = CodeMirror.fromTextArea(this.source.el, {
	        mode: {name: "python",
	               version: 2,
	               singleLineStringErrors: false},
	        lineNumbers: true,
	        indentUnit: 4,
	        tabMode: "shift",
	        matchBrackets: true
	    });
		this.source_group.onCollapseChanged = function() { 
			thizz.positionTerminals();
			thizz.editor.refresh();
		};
		$(this.bodyEl).css('border-color', 'green').prev().css('background-color', 'green');
	},
	   
	/**
     * Create (and re-create) the terminals with this.nParams input terminals
     * 
     * @method createTerminals
     */
	createTerminals: function(event) {
		
		// Input terminal
		if( !this.inputTerminal ) {
			this.inputTerminal = this.addTerminal({xtype: "WireIt.util.TerminalInput", name: "in", nMaxWires: Infinity});  
			this.inputTerminal.CodeBoxContainer = this;
		}
		
		// Exception terminal
		if ( ! this.exceptionTerminal) {
			this.exceptionTerminal = this.addTerminal({xtype: "WireIt.util.TerminalOutput", name: "exception", direction: [1,0]});      
			$(this.exceptionTerminal.el).append($('<div></div>').addClass('code_terminal_label').text("exception")).removeAttr('title');
			WireIt.sn(this.exceptionTerminal.el, null, {position: "absolute", right: "-15px", bottom: "30px"});
			this.exceptionTerminal.CodeBoxContainer = this;
		}
		      
		// Outlet terminals :
		var new_terminal_list = [];
		var thizz = this;
		$.each(this.outlets_list.subFields, function (i, outlet) {
			if ( ! outlet.term ) {
		        var term = thizz.addTerminal({xtype: "WireIt.util.TerminalOutput", "name": outlet.getValue() || "outlet"});
		        var label = $('<div></div>').addClass('code_terminal_label').text(outlet.getValue());
		        $(term.el).append(label).removeAttr('title');
		        WireIt.sn(term.el, null, {position: "absolute", bottom: "-15px"});
		        outlet.term = term;
		        outlet.updatedEvt.subscribe(function (event) {
		        	label.text(outlet.getValue());
		        	term.options.name = outlet.getValue();
		        });
			}
			new_terminal_list.push(outlet.term);
		});
		$.each(this.outlet_terminals, function(i, terminal) {
			if (new_terminal_list.indexOf(terminal) == -1) {
				terminal.remove();
			}
		});
		this.outlet_terminals = new_terminal_list;
		this.terminals = $.merge([], new_terminal_list);
		this.terminals.push(this.inputTerminal);
		this.terminals.push(this.exceptionTerminal);
		
		this.positionTerminals();
	    // Declare the new terminals to the drag'n drop handler (so the wires are moved around with the container)
		this.dd.setTerminals(this.terminals);
	},

	/**
     * Reposition the terminals
     * 
     * @method positionTerminals
     */
	positionTerminals: function() {
        var width = WireIt.getIntStyle(this.el, "width");
        var height = WireIt.getIntStyle(this.el, "height");

        var outputsInterval = Math.floor(width/(this.outlet_terminals.length+1));
        
        $.each(this.outlet_terminals, function (i, terminal) {
	        YAHOO.util.Dom.setStyle(terminal.el, "left", (outputsInterval*(i+1))-15+"px" );
	        $.each(terminal.wires, function (j, wire) {
	        	wire.redraw();
	        });
        });
	      
	    // Input terminal
	    WireIt.sn(this.inputTerminal.el, null, {position: "absolute", top: "-15px", left: (Math.floor(width/2)-15)+"px"});
        $.each(this.inputTerminal.wires, function (j, wire) {
        	wire.redraw();
        });

        // Exception terminal
	    WireIt.sn(this.exceptionTerminal.el, null, {position: "absolute", right: "-15px", top: (Math.floor(height/2)-15)+"px"});
        $.each(this.exceptionTerminal.wires, function (j, wire) {
        	wire.redraw();
        });
	},
	   
	/**
     * Extend the getConfig to add the "codeText" property
     * 
     * @method getConfig
     */
	getConfig: function() {
		this.editor.save();

		var obj = CodeBoxContainer.superclass.getConfig.call(this);
		obj.sourceDef = this.form.getValue();
	    return obj;
	}
	   
});

var FlowCodeContainer = function(options, layer) {
    FlowCodeContainer.superclass.constructor.call(this, options, layer);
    this.outlet_terminals = [];
    this.buildTextArea(options || {});
       
    this.createTerminals();
};

YAHOO.extend(FlowCodeContainer, WireIt.Container, {
       
    /**
     * Create the textarea for the javascript code
     * 
     * @method buildTextArea
     * @param {String}
     *            codeText
     */
    buildTextArea: function(config) {
        var unique_id = 'xxxxxxxx-xxxx-xxxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {var r = Math.random()*16|0,v=c=='x'?r:r&0x3|0x8;return v.toString(16);});

        var formDef = {
            "parentEl": this.bodyEl,
            "name" : "",
            "legend" : "",
            "collapsible" : false,
            "collapsed" : false,
            "fields" : 
            [
                {
                    "type" : "string",
                    "inputParams" : 
                    {
                        "name" : "id",
                        "label" : "Identifier",
                        "required" : true,
                        "showMsg" : false,
                        "typeInvite" : "Enter id",
                        "value" : ""
                    }
                },
                {
                    "type" : "text",
                    "inputParams" : 
                    {
                        "name" : "javascript_code",
                        "label" : "",
                        "required" : false,
                        "showMsg" : false,
                        "typeInvite" : "",
                        "cols" : 0,
                        "rows" : 0,
                        "value" : 'var run = function(rogerthat, messageFlowRun){\n    /* do some calculations */\n    /* return name of next step */\n    var nextStepResult = {};\n    nextStepResult.outlet = \"default\";\n    nextStepResult.defaultValue = null; /* This is not required */\n    return nextStepResult;\n};',
                        "className": "rogerthat-hidden javascript-code-" + unique_id
                    }
                },
                {
                    "type" : "hidden",
                    "inputParams" :
                    {
                        "name" : "button-editor-name-" + unique_id,
                        "value" : "",
                        "className": "button-editor-class-" + unique_id
                    }
                },
                {
                    "type" : "group",
                    "inputParams" : 
                    {
                        "name" : "outlets_group",
                        "legend" : "Outlets",
                        "collapsible" : true,
                        "collapsed" : true,
                        "fields" : 
                        [
                            {
                                "type" : "list",
                                "inputParams" : 
                                {
                                    "name" : "outlets_list",
                                    "listAddLabel" : "Add outlet",  
                                    "elementType" : {
                                        "type" : "string",
                                        "inputParams" : {
                                            "name" : "name",
                                            "label" : "Name",
                                            "required" : true,
                                            "showMsg" : false,
                                            "minLength" : 1,
                                            "value" : ""
                                        }
                                    },
                                    "value" : ["default"]
                                }
                            }

                        ],
                        "value" : {
                            "outlets_list" : ["default"]
                        }
                    }
                }
            ]
        };
        var thizz = this;
        this.form = new YAHOO.inputEx.Group(formDef);
        
        if (config.sourceDef) {
            this.form.setValue(config.sourceDef);
        }
        
        $( ".button-editor-class-" + unique_id).replaceWith( "<input id=\"button-editor-button-" + unique_id + "\" unique_id=\"" + unique_id + "\" type=\"submit\" value=\"Open editor\">" );
        
        var flowCodeEditor = null;
        var flowCodeDialog = null;
        var isClosingFlowCodeDialog = false;
        var saveJavascriptCode = function() {
            var jsCode = flowCodeEditor.getValue();
            $(".javascript-code-"+ unique_id + " textarea[name='javascript_code']").val(jsCode);
            this.editor.markUnsaved();
        };
                
        $("#button-editor-button-" + unique_id).click(function () {
            $("#container-"+ unique_id).remove();
            flowCodeDialog = $('<div id="container-' + unique_id + '" style="height: 100%; width: 100%; text-align:left;"><textarea id="txt-' + unique_id + '" style="height: 100%; width: 98%;" ></textarea></div>').clone().dialog({
                title : 'Flow code: Javascript editor',
                width : window.innerWidth - 50,
                height : window.innerHeight - 50,
                modal : true,
                close: function () {
                    if (!isClosingFlowCodeDialog)
                        saveJavascriptCode();
                    isClosingFlowCodeDialog = false;
                },
                buttons : {
                    Close : function() {
                        saveJavascriptCode();
                        isClosingFlowCodeDialog = true;
                        flowCodeDialog.dialog('close');
                    }
                }
            }).dialog('open');

            flowCodeEditor = CodeMirror.fromTextArea($("#txt-"+ unique_id)[0], {
                mode: {name: "javascript", json: true},
                lineNumbers: true,
                indentUnit: 4,
                tabMode: "shift",
                matchBrackets: true
            });
                        
            var currentJsCode = $(".javascript-code-"+ unique_id + " textarea[name='javascript_code']").val();
            if (currentJsCode == "") {
                flowCodeEditor.setValue("var run = function(rogerthat, messageFlowRun){\n    /* do some calculations */\n    /* return name of next step */\n    var nextStepResult = {};\n    nextStepResult.outlet = \"default\";\n    nextStepResult.defaultValue = null; /* This is not required */\n    return nextStepResult;\n};");
            }
            else{
                flowCodeEditor.setValue(currentJsCode);
            }
            $("#container-"+ unique_id + " .cm-s-default").css("background-color", "#fff");
            $(".CodeMirror").css("color", "#000");
            $("div.CodeMirror-scroll").css("height",  window.innerHeight - 160);
        });
        
        this.outlets_group = this.form.getFieldByName('outlets_group');
        this.outlets_group.onCollapseChanged = function() { thizz.positionTerminals(); };
        this.outlets_list = this.outlets_group.getFieldByName('outlets_list');
        this.outlets_list.updatedEvt.subscribe(function (event) {thizz.createTerminals(event);});
    },
       
    /**
     * Create (and re-create) the terminals with this.nParams input terminals
     * 
     * @method createTerminals
     */
    createTerminals: function(event) {
        
        // Input terminal
        if( !this.inputTerminal ) {
            this.inputTerminal = this.addTerminal({xtype: "WireIt.util.TerminalInput", name: "in", nMaxWires: Infinity});  
            this.inputTerminal.FlowCodeContainer = this;
        }
        
        // Exception terminal
        if ( ! this.exceptionTerminal) {
            this.exceptionTerminal = this.addTerminal({xtype: "WireIt.util.TerminalOutput", name: "exception", direction: [1,0], nMaxWires: 1});
            $(this.exceptionTerminal.el).append($('<div></div>').addClass('code_terminal_label').text("exception")).removeAttr('title');
            WireIt.sn(this.exceptionTerminal.el, null, {position: "absolute", right: "-15px", bottom: "30px"});
            this.exceptionTerminal.FlowCodeContainer = this;
        }
              
        // Outlet terminals :
        var new_terminal_list = [];
        var thizz = this;
        $.each(this.outlets_list.subFields, function (i, outlet) {
            if ( ! outlet.term ) {
                var term = thizz.addTerminal({xtype: "WireIt.util.TerminalOutput", "name": outlet.getValue() || "outlet", nMaxWires: 1});
                var label = $('<div></div>').addClass('code_terminal_label').text(outlet.getValue());
                $(term.el).append(label).removeAttr('title');
                WireIt.sn(term.el, null, {position: "absolute", bottom: "-15px"});
                outlet.term = term;
                outlet.updatedEvt.subscribe(function (event) {
                    label.text(outlet.getValue());
                    term.options.name = outlet.getValue();
                });
            }
            new_terminal_list.push(outlet.term);
        });
        $.each(this.outlet_terminals, function(i, terminal) {
            if (new_terminal_list.indexOf(terminal) == -1) {
                terminal.remove();
            }
        });
        this.outlet_terminals = new_terminal_list;
        this.terminals = $.merge([], new_terminal_list);
        this.terminals.push(this.inputTerminal);
        this.terminals.push(this.exceptionTerminal)
        
        this.positionTerminals();
        // Declare the new terminals to the drag'n drop handler (so the wires are moved around with the container)
        this.dd.setTerminals(this.terminals); 
    },

    /**
     * Reposition the terminals
     * 
     * @method positionTerminals
     */
    positionTerminals: function() {
        var width = WireIt.getIntStyle(this.el, "width");
        var height = WireIt.getIntStyle(this.el, "height");

        var outputsInterval = Math.floor(width/(this.outlet_terminals.length+1));
        
        $.each(this.outlet_terminals, function (i, terminal) {
            YAHOO.util.Dom.setStyle(terminal.el, "left", (outputsInterval*(i+1))-15+"px" );
            $.each(terminal.wires, function (j, wire) {
                wire.redraw();
            });
        });
          
        // Input terminal
        WireIt.sn(this.inputTerminal.el, null, {position: "absolute", top: "-15px", left: (Math.floor(width/2)-15)+"px"});
        $.each(this.inputTerminal.wires, function (j, wire) {
            wire.redraw();
        });

        // Exception terminal
        WireIt.sn(this.exceptionTerminal.el, null, {position: "absolute", right: "-15px", top: (Math.floor(height/2)-15)+"px"});
        $.each(this.exceptionTerminal.wires, function (j, wire) {
            wire.redraw();
        });
    },
       
    /**
     * Extend the getConfig to add the "codeText" property
     * 
     * @method getConfig
     */
    getConfig: function() {
        var obj = FlowCodeContainer.superclass.getConfig.call(this);
        obj.sourceDef = this.form.getValue();
        return obj;
    }
       
});


var FormWidgetContainer = function(options, layer) {
    FormWidgetContainer.superclass.constructor.call(this, options, layer);
};

YAHOO.lang.extend(FormWidgetContainer, WireIt.FormContainer, {

    initTerminals: function(terms) {
        FormWidgetContainer.superclass.initTerminals.call(this, terms);
        $.each(this.terminals, function (i, term) {
            if (term.options.name == 'positive' || term.options.name == 'negative') {
                $(term.el).addClass(term.options.name + '_terminal');
            }
        });
    }

});

var SubMessageFlowContainer = function(options, layer) {
    SubMessageFlowContainer.superclass.constructor.call(this, options, layer);
};

YAHOO.lang.extend(SubMessageFlowContainer, WireIt.FormContainer, {

    setOptions: function(options) {
        SubMessageFlowContainer.superclass.setOptions(options);
        this.options.fields = [
            {
                "type" : "select",
                "inputParams" :
                {
                    "name" : "nmessage_flow",
                    "label" : "Message flow",
                    "selectValues" : sub_messageflow_keys,
                    "selectOptions" : sub_messageflow_names,
                    "value" : ""
                }
            }
        ];
    }
});

var JavascriptValidationFormWidgetContainer = function(options, layer) {
    JavascriptValidationFormWidgetContainer.superclass.constructor.call(this, options, layer);
    this.outlet_terminals = [];
    this.buildTextArea(options || {});
       
    this.createTerminals();
};

var getJavascriptValidationFormDef = function(thizz, unique_id, title) {
    var validateCode = {
        "type" : "text",
        "inputParams" : 
        {
            "name" : "javascript_validation",
            "label" : "",
            "required" : false,
            "showMsg" : false,
            "typeInvite" : "",
            "cols" : 0,
            "rows" : 0,
            "value": null,
            "className": "rogerthat-hidden javascript-validation-" + unique_id
        }
    };
    
    var validateBtn = {
        "type" : "hidden",
        "inputParams" :
        {
            "name" : "button-editor-name-" + unique_id,
            "value" : "",
            "className": "button-editor-class-" + unique_id
        }
    };
    
    var formDef = {
        "parentEl": thizz.bodyEl,
        "name": "",
        "legend": "",
        "collapsible" : false,
        "collapsed" : false,
        "fields": [
            formId,
            formMessage,
            formMessageGroup
        ],
    };
    
    var formSettingsGroup = {
        "type" : "group",
        "inputParams" : 
        {
            "name" : "form_settings_group",
            "legend" : "Form settings",
            "collapsible" : true,
            "collapsed" : true,
            "fields" : formGroupFields
        }
    };
    if (title == "Text line" || title == "Text autocomplete") {
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat(textFormFields);
    } else if (title == "Text block") {
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat(textBlockFields);
    } else if (title == "Single select") {
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "string",
            "inputParams" : {
                "name" : "value",
                "label" : "Initially selected choice",
                "typeInvite" : "Enter selected choice id",
                "description" : "Identifier of the initially selected choice",
                "required" : false
            }
        });
        
    } else if (title == "Date select") {
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "select",
            "inputParams" :
            {
                "name" : "mode",
                "label" : "Mode",
                "selectValues" : ["date", "time", "date_time"],
                "selectOptions" : ["Date", "Time", "Date and time"],
                "value" : "date"
            }
        });
        
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "select",
            "inputParams" : {
                "name" : "minute_interval",
                "label" : "Minute interval",
                "selectValues" : ["1", "5", "10", "15", "20", "30"],
                "selectOptions" : ["1", "5", "10", "15", "20", "30"],
                "value" : "15"
            }
        });
        
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "string",
            "inputParams" : {
                "name" : "unit",
                "label" : "Unit",
                "required" : false,
                "showMsg" : false,
                "typeInvite" : "Enter unit",
                "description" : "Eg: Date of birth: &lt;value/&gt;",
                "value" : "<value/>"
            }
        });
    } else if (title == "Single slider") {
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat(sliderFormFields);
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "string",
            "inputParams" : {
                "name" : "unit",
                "label" : "Unit",
                "required" : false,
                "showMsg" : false,
                "typeInvite" : "Enter unit",
                "description" : "Eg: &lt;value/&gt; years",
                "value" : "<value/>"
            }
        });
        
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "float",
            "inputParams" : {
                "name" : "value",
                "label" : "Value",
                "typeInvite" : "Enter initial value",
                "negative" : true,
                "required" : false
            }
        });
    } else if (title == "Range slider") {
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat(sliderFormFields);
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "string",
            "inputParams" : {
                "name" : "unit",
                "label" : "Unit",
                "required" : false,
                "showMsg" : false,
                "typeInvite" : "Enter unit",
                "description" : "Eg: Between &lt;low_value/&gt; and &lt;high_value/&gt;",
                "value" : "<low_value/> - <high_value/>"
            }
        });
        
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "float",
            "inputParams" : {
                "name" : "low_value",
                "label" : "Low value",
                "typeInvite" : "Enter initial low value",
                "negative" : true,
                "required" : false
            }
        });
        
        formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat({
            "type" : "float",
            "inputParams" : {
                "name" : "high_value",
                "label" : "High value",
                "typeInvite" : "Enter initial high value",
                "negative" : true,
                "required" : false
            }    
        });
    }
    
    formSettingsGroup.inputParams.fields = formSettingsGroup.inputParams.fields.concat(validateCode).concat(validateBtn);
    
    formDef.fields.push(formSettingsGroup);
    
    if (title == "Text autocomplete") {
        formDef.fields.push(formSuggestionsGroup);
    } else if (title == "Single select") {
        formDef.fields.push(formChoicesGroup);
    } else if (title == "Multi select") {
        formDef.fields.push(formChoicesGroup);
        formDef.fields.push(formInitialChoicesGroup);
    }
    
    formDef.fields.push(formAttachmentsGroup);
    return formDef;
};

YAHOO.extend(JavascriptValidationFormWidgetContainer, WireIt.Container, {
    
    buildTextArea: function(config) {
        var unique_id = 'xxxxxxxx-xxxx-xxxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {var r = Math.random()*16|0,v=c=='x'?r:r&0x3|0x8;return v.toString(16);});
        var currentJsCode = '',
            javascriptValidationEditor = null,
            javascriptValidationDialog = null,
            codeTextArea,
            isClosingJavascriptValidationDialog = false;
        
        this.form = new YAHOO.inputEx.Group(getJavascriptValidationFormDef(this, unique_id, config.title));
        
        if (config.formMessageDef) {
            this.form.setValue(config.formMessageDef);
        }
        
        $( ".button-editor-class-" + unique_id).replaceWith( "<input id=\"button-editor-button-" + unique_id + "\" unique_id=\"" + unique_id + "\" type=\"submit\" value=\"Open validation editor\">" );

        var saveJavascriptCode = function() {
            var jsCode = javascriptValidationEditor.getValue();
            if (jsCode !== DEFAULT_JS_VALIDATION_CODE) {
                this.editor.markUnsaved();
                $(".javascript-validation-" + unique_id + " textarea[name='javascript_validation']").val(jsCode);
                currentJsCode = jsCode;
            } else {
                codeTextArea.val('');
            }
        };

        $("#button-editor-button-" + unique_id).click(function () {
            $("#container-"+ unique_id).remove();
            javascriptValidationDialog = $('<div id="container-' + unique_id + '" style="height: 100%; width: 100%; text-align:left;"><textarea id="txt-' + unique_id + '" style="height: 100%; width: 98%;" ></textarea></div>').dialog({
                title : config.title + ': Javascript editor',
                width : window.innerWidth - 50,
                height : window.innerHeight - 50,
                modal : true,
                close: function () {
                    if (!isClosingJavascriptValidationDialog)
                        saveJavascriptCode();
                    isClosingJavascriptValidationDialog = false;
                },
                buttons : {
                    Close : function() {
                        saveJavascriptCode();
                        isClosingJavascriptValidationDialog = true;
                        javascriptValidationDialog.dialog('close');
                    }
                }
            }).dialog('open');
            codeTextArea = $("#txt-" + unique_id);

            javascriptValidationEditor = CodeMirror.fromTextArea(codeTextArea[0], {
                mode: {name: "javascript", json: true},
                lineNumbers: true,
                indentUnit: 4,
                tabMode: "shift",
                matchBrackets: true
            });
            var currentJsCode = $(".javascript-validation-"+ unique_id).find("textarea[name='javascript_validation']").val();
            javascriptValidationEditor.setValue(currentJsCode || DEFAULT_JS_VALIDATION_CODE);

            $("#container-"+ unique_id + " .cm-s-default").css("background-color", "#fff");
            $(".CodeMirror").css("color", "#000");
            $("div.CodeMirror-scroll").css("height",  window.innerHeight - 160);
        });
    },
       
    createTerminals: function(event) {
        // Input terminal
        if( !this.inputTerminal ) {
            this.inputTerminal = this.addTerminal({xtype: "WireIt.util.TerminalInput", name: "in", nMaxWires: Infinity});  
            this.inputTerminal.JavascriptValidationFormWidgetContainer = this;
        }
        
        // Outlet terminals :
        var new_terminal_list = [];
        var thizz = this;
        $.each(["positive", "negative"], function (i, name) {
            var term = thizz.addTerminal({xtype: "WireIt.util.TerminalOutput", "name": name || "outlet", nMaxWires: 1});
            $(term.el).addClass(name + '_terminal').attr('title', name);
            WireIt.sn(term.el, null, {position: "absolute", bottom: "-15px"});
            new_terminal_list.push(term);
        });
        $.each(this.outlet_terminals, function(i, terminal) {
            if (new_terminal_list.indexOf(terminal) == -1) {
                terminal.remove();
            }
        });
        this.outlet_terminals = new_terminal_list;
        this.terminals = $.merge([], new_terminal_list);
        this.terminals.push(this.inputTerminal);
        
        this.positionTerminals();
        // Declare the new terminals to the drag'n drop handler (so the wires are moved around with the container)
        this.dd.setTerminals(this.terminals); 
    },

    positionTerminals: function() {
        var width = WireIt.getIntStyle(this.el, "width");
        var height = WireIt.getIntStyle(this.el, "height");

        $.each(this.outlet_terminals, function (i, terminal) {
            if (i == 0) {
                YAHOO.util.Dom.setStyle(terminal.el, "left", "86px");
            } else {
                YAHOO.util.Dom.setStyle(terminal.el, "right", "86px");
            }
            $.each(terminal.wires, function (j, wire) {
                wire.redraw();
            });
        });
          
        // Input terminal
        WireIt.sn(this.inputTerminal.el, null, {position: "absolute", top: "-15px", left: (Math.floor(width/2)-15)+"px"});
        $.each(this.inputTerminal.wires, function (j, wire) {
            wire.redraw();
        });
    },
       
    getConfig: function() {
        var obj = JavascriptValidationFormWidgetContainer.superclass.getConfig.call(this);
        obj.formMessageDef = this.form.getValue();
        return obj;
    }
       
});

$(document).bind('change', function (e) {
    "use strict";
    var $this = $(e.target);
    if ($this.attr('name') === 'global_branding') {
        $('[name=branding]').val($this.val());
    }
});