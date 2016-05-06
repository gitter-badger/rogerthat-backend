(function() {
    var util = YAHOO.util,lang = YAHOO.lang;
    var Event = util.Event, Dom = util.Dom, Connect = util.Connect,JSON = lang.JSON,widget = YAHOO.widget;


/**
 * Module Proxy handle the drag/dropping from the module list to the layer (in the WiringEditor)
 * @class ModuleProxy
 * @constructor
 * @param {HTMLElement} el
 * @param {WireIt.WiringEditor} WiringEditor
 */
WireIt.ModuleProxy = function(el, WiringEditor) {
   
   this._WiringEditor = WiringEditor;
   
   // Init the DDProxy
   WireIt.ModuleProxy.superclass.constructor.call(this,el, "module", {
        dragElId: "moduleProxy"
    });
    
    this.isTarget = false; 
};
YAHOO.extend(WireIt.ModuleProxy,YAHOO.util.DDProxy, {
   
   /**
    * copy the html and apply selected classes
    * @method startDrag
    */
   startDrag: function(e) {
      WireIt.ModuleProxy.superclass.startDrag.call(this,e);
       var del = this.getDragEl(),
			  lel = this.getEl();
       del.innerHTML = lel.innerHTML;
       del.className = lel.className;
   },
   
   /**
    * Override default behavior of DDProxy
    * @method endDrag
    */
   endDrag: function(e) {},
    
   /**
    * Add the module to the WiringEditor on drop on layer
    * @method onDragDrop
    */
   onDragDrop: function(e, ddTargets) { 
      // The layer is the only target :
      var layerTarget = ddTargets[0],
			 layer = ddTargets[0]._layer,
			 del = this.getDragEl(),
			 pos = YAHOO.util.Dom.getXY(del),
			 layerPos = YAHOO.util.Dom.getXY(layer.el);
      this._WiringEditor.addModule( this._module ,[pos[0]-layerPos[0]+layer.el.scrollLeft, pos[1]-layerPos[1]+layer.el.scrollTop]);
    }
   
});


/**
 * The WiringEditor class provides a full page interface 
 * @class WiringEditor
 * @constructor
 * @param {Object} options
 */
WireIt.WiringEditor = function(options) {
	
	 /**
	  * Hash object to reference module definitions by their name
	  * @property modulesByName
	  * @type {Object}
	  */
    this.modulesByName = {};

    // set the default options
    this.setOptions(options);
    
    /**
     * Container DOM element
     * @property el
     */
    this.el = Dom.get(options.parentEl);
    
    /**
     * @property layout
     * @type {YAHOO.widget.Layout}
     */
    this.layout = new widget.Layout(this.el, this.options.layoutOptions);
    this.layout.render();

	 // Right accordion
    this.renderAccordion();

    /**
     * @property layer
     * @type {WireIt.Layer}
     */
    this.layer = new WireIt.Layer(this.options.layerOptions);
	this.layer.eventChanged.subscribe(this.onLayerChanged, this, true);

	 /**
	  * @property leftEl
	  * @type {DOMElement}
	  */
    this.leftEl = Dom.get('left');
    this.modulesEl = Dom.get('modules');

    // Render module list
    this.buildModulesList();

    // Render buttons
    this.renderButtons();

 	// Saved status
	this.renderSavedStatus();

    // Properties Form
    this.renderPropertiesForm();

	// LoadWirings
	if( this.adapter.init && YAHOO.lang.isFunction(this.adapter.init) ) {
			this.adapter.init();
 	}
	this.load();
};

WireIt.WiringEditor.prototype = {

 /**
  * @method setOptions
  * @param {Object} options
  */
 setOptions: function(options) {
    
    /**
     * @property options
     * @type {Object}
     */
    this.options = {};
    
    // Load the modules from options
    this.modules = options.modules || [];
    for(var i = 0 ; i < this.modules.length ; i++) {
       var m = this.modules[i];
       this.modulesByName[m.name] = m;
    }

	 this.adapter = options.adapter || WireIt.WiringEditor.adapters.JsonRpc;
     
    this.options.languageName = options.languageName || 'anonymousLanguage';
    
    this.options.propertiesFields = options.propertiesFields || [
		{"type": "string", inputParams: {"name": "name", label: "Title", typeInvite: "Enter a title" } },
		{"type": "text", inputParams: {"name": "description", label: "Description", cols: 30, rows: 4} }
	 ];
    
    this.options.layoutOptions = options.layoutOptions || {
	 	units: [
	   	{ position: 'top', height: 50, body: 'top'},
	      { position: 'left', width: 200, resize: true, body: 'left', gutter: '5px', collapse: true, 
	        collapseSize: 25, header: 'Modules', scroll: true, animate: true },
	      { position: 'center', body: 'center', gutter: '5px' },
	      { position: 'right', width: 320, resize: true, body: 'right', gutter: '5px', collapse: true, 
	        collapseSize: 25, /*header: 'Properties', scroll: true,*/ animate: true }
	   ]
	};
     
    this.options.layerOptions = {};
    var layerOptions = options.layerOptions || {};
    this.options.layerOptions.parentEl = layerOptions.parentEl ? layerOptions.parentEl : Dom.get('center');
    this.options.layerOptions.layerMap = YAHOO.lang.isUndefined(layerOptions.layerMap) ? true : layerOptions.layerMap;
    this.options.layerOptions.layerMapOptions = layerOptions.layerMapOptions || { parentEl: 'layerMap' };

	 this.options.accordionViewParams = options.accordionViewParams || {
												collapsible: false, 
												expandable: true, // remove this parameter to open only one panel at a time
												width: '308px', 
												expandItem: 0, 
												animationSpeed: '0.3', 
												animate: true, 
												effect: YAHOO.util.Easing.easeBothStrong
											};
 },

	
	/**
	 * Render the accordion using yui-accordion
  	 */
	renderAccordion: function() {
		this.accordionView = new YAHOO.widget.AccordionView('accordionView', this.options.accordionViewParams);
	},
 
 /**
  * Render the properties form
  * @method renderPropertiesForm
  */
 renderPropertiesForm: function() {
    this.propertiesForm = new inputEx.Group({
       parentEl: YAHOO.util.Dom.get('propertiesForm'),
       fields: this.options.propertiesFields
    });

	this.propertiesForm.updatedEvt.subscribe(function() {
		this.markUnsaved();
	}, this, true);
 },
 
 /**
  * Build the left menu on the left
  * @method buildModulesList
  */
 buildModulesList: function() {

     var modules = this.modules;
     for(var i = 0 ; i < modules.length ; i++) {
		  this.addModuleToList(modules[i]);
     }

     // Make the layer a drag drop target
     if(!this.ddTarget) {
       this.ddTarget = new YAHOO.util.DDTarget(this.layer.el, "module");
       this.ddTarget._layer = this.layer;
     }
     
 },

 /**
  * Add a module definition to the left list
  */
 addModuleToList: function(module) {
	
		var div = WireIt.cn('div', {className: "WiringEditor-module"});
      if(module.container.icon) {
         div.appendChild( WireIt.cn('img',{src: module.container.icon}) );
      }
      div.appendChild( WireIt.cn('span', null, null, module.name) );

      var ddProxy = new WireIt.ModuleProxy(div, this);
      ddProxy._module = module;

      this.modulesEl.appendChild(div);
 },
 
 /**
  * add a module at the given pos
  */
 addModule: function(module, pos) {
    try {
       var containerConfig = module.container;
       containerConfig.position = pos;
       containerConfig.title = module.name;
       var container = this.layer.addContainer(containerConfig);
       Dom.addClass(container.el, "WiringEditor-module-"+module.name);
    }
    catch(ex) {
       this.alert("Error Layer.addContainer: "+ ex.message);
    }    
 },

 /**
  * Toolbar
  * @method renderButtons
  */
 renderButtons: function() {
    var toolbar = Dom.get('toolbar');
    // Buttons :
    var newButton = new widget.Button({ label:"New", id:"WiringEditor-newButton", container: toolbar });
    newButton.on("click", this.onNew, this, true);

    var loadButton = new widget.Button({ label:"Load", id:"WiringEditor-loadButton", container: toolbar });
    loadButton.on("click", this.load, this, true);

    var saveButton = new widget.Button({ label:"Save", id:"WiringEditor-saveButton", container: toolbar });
    saveButton.on("click", this.onSave, this, true);

    var deleteButton = new widget.Button({ label:"Delete", id:"WiringEditor-deleteButton", container: toolbar });
    deleteButton.on("click", this.onDelete, this, true);

    var importButton = new widget.Button({ label:"Import Design", id:"WiringEditor-importButton", container: toolbar });
    importButton.on("click", this.onImport, this, true);
    
    var exportButton = new widget.Button({ label:"Export Design", id:"WiringEditor-exportButton", container: toolbar });
    exportButton.on("click", this.onDownloadDesign, this, true);

    var exportXMLButton = new widget.Button({ label:"Export XML Definition", id:"WiringEditor-exportXMLButton", container: toolbar });
    exportXMLButton.on("click", this.onDownloadXML, this, true);
    
    var tryButton = new widget.Button({ label:"Try ...", id:"WiringEditor-tryButton", container: toolbar });
    tryButton.on("click", this.onTry, this, true);
},

	/**
	 * @method renderSavedStatus
	 */
	renderSavedStatus: function() {
		var top = Dom.get('top');
		this.savedStatusEl = WireIt.cn('div', {className: 'savedStatus', title: 'Not saved'}, {display: 'none'});
		$(this.savedStatusEl)
			.append($('<span></span>').css('font-size', '27pt').text('*'))
			.append($('<span></span>').css('vertical-align', 'top').css('line-height', '27px').css('padding-left', '5px').css('padding-right', '5px').text('pending changes'))
			.append($('<span></span>').css('font-size', '27pt').text('*'));
		top.appendChild(this.savedStatusEl);
	},

 /**
  * save the current module
  * @method saveModule
  */
 saveModule: function(force) {
	 
    var value = this.getValue();
    
    if(value.name === "") {
    	mctracker.alert("Please choose a name");
       return;
    }
    
    mctracker.showProcessing();

    this.tempSavedWiring = {name: value.name, multilanguage: value.working.properties.multilanguage, working: JSON.stringify(value.working), language: this.options.languageName , force: force ? "true" : "false" };
                
    this.adapter.saveWiring(this.tempSavedWiring, {
       success: this.saveModuleSuccess,
       failure: this.saveModuleFailure,
       scope: this
    });

 },

 /**
  * saveModule success callback
  * @method saveModuleSuccess
  */
saveModuleSuccess: function(o) {
    var STATUS_VALID = 0;
    var STATUS_BROKEN = 1;
    var STATUS_SUBFLOWS_BROKEN = 2;
    var thizz = this;

    if ( o == null || o.error ) {
        mctracker.hideProcessing();
        mctracker.alert("Unable to save the message flow: " + o.error);
    } else {
        if ( o.status == STATUS_VALID || o.force ) {
            this.markSaved();
            loadMessageFlows();
            mctracker.hideProcessing("Saved successfully!");
        } else {
            mctracker.hideProcessing();
            var error_message = "<div style='text-align: left;'><span style='font-weight: bold;'>This message flow is invalid due to following error:</span><br><br><hr>";
            if (o.error_message) {
                error_message += mctracker.htmlEncode(o.error_message);
            } else if (o.broken_sub_flows) {
                error_message += "You are using the following message flows which are not valid: " + o.broken_sub_flows.join(", ");
            }
            error_message += "<hr><br>Do you want to cancel and correct the problem or force the save action and possibly break this message flow and its parent message flows?</div>";
            mctracker.confirm(error_message, function () {
                thizz.saveModule(true);
            }, null, "Continue with save & break flow", null, "Error", true, 400);
        }
    }
},

 /**
  * saveModule failure callback
  * @method saveModuleFailure
  */
saveModuleFailure: function(errorStr) {
	mctracker.hideProcessing();
	mctracker.alert("Unable to save the wiring : "+errorStr);
},

alert: function(txt) {
	mctracker.alert(mctracker.htmlize(txt), null, null, null, true);
},

 /**
  * Download design as XML
  * @method onDownload
  */
 onDownloadXML: function() {
     var thizz = this;
     var name = this.getValue().name;
     if(!this.isSaved() || ! name) {
         this.alert("You need to save your work before you can export it!");
         return;
     }    
    window.location.href = '/mobi/rest/services/mfd/download?name='+encodeURIComponent(thizz.getValue().name)+'&type=XML';		
 },
 
 onImport: function () {
     var thizz = this;
     this.confirmContinueWithoutSaving(function () {
         mctracker.input("Paste the exported design source in the input field:", function (source) {
             try {
                 var wiring = JSON.parse(source);           

                 thizz.preventLayerChangedEvent = true;
                 
             // Force wirings on screen
             jQuery.each(wiring.modules, function (i, module) {
                 jQuery.each(module.config.position, function (j, coord) {
                     if (coord < 0)
                         module.config.position[j] = coord * -1;
                 });
             });

             // TODO: check if current wiring is saved...
              thizz.layer.clear();
             
              thizz.propertiesForm.setValue(wiring.properties, false); // the false tells inputEx to NOT fire the updatedEvt
             
             if(lang.isArray(wiring.modules)) {
               
                // Containers
                for(i = 0 ; i < wiring.modules.length ; i++) {
                   var m = wiring.modules[i];
                   if(thizz.modulesByName[m.name]) {
                      var baseContainerConfig = thizz.modulesByName[m.name].container;
                      YAHOO.lang.augmentObject(m.config, baseContainerConfig); 
                      m.config.title = m.name;
                      var container = thizz.layer.addContainer(m.config);
                      Dom.addClass(container.el, "WiringEditor-module-"+m.name);
                      container.setValue(m.value);
                   }
                   else {
                      throw new Error("WiringEditor: module '"+m.name+"' not found !");
                   }
                }
                
                // Wires
                if(lang.isArray(wiring.wires)) {
                    for(i = 0 ; i < wiring.wires.length ; i++) {
                       // On doit chercher dans la liste des terminaux de chacun des modules l'index des terminaux...
                        thizz.layer.addWire(wiring.wires[i]);
                    }
                 }
              }
              
             
             thizz.preventLayerChangedEvent = false;
                 return true;
             } catch (err) {
                 mctracker.alert("Could not parse the design.");
             }
         }, null, true);
     });
 },

 /**
  * Download design
  * @method onDownload
  */
 onDownloadDesign: function() {
    var thizz = this;
    var name = this.getValue().name;
    if(!this.isSaved() || ! name) {
        this.alert("You need to save your work before you can export it!");
        return;
    }    
    window.location.href = '/mobi/rest/services/mfd/download?name='+encodeURIComponent(thizz.getValue().name)+'&type=json';       
 },

 onTry: function() {
	var thizz = this; 
	if(!this.isSaved()) {
		this.alert("You need to save your work before you can execute it!");
		return;
	}
    var name = this.getValue().name;
    var account = this.getValue().working.properties.test_account;
	if (! account) {
		this.alert('You need to enter a Rogerthat account to continue!');
		return;
	}
	mctracker.showProcessing();
	mctracker.call({
		url: '/mobi/rest/mfd/test',
		type: 'POST',
		data: {
			data: JSON.stringify({
				message_flow_design_name: name,
				member: account,
				force_language: this.getValue().working.properties.test_language
			})
		},
		success: function (data, textStatus, XMLHttpRequest) {
			if (!data)
				mctracker.hideProcessing("Flow scheduled!");
			else {
				mctracker.hideProcessing();
				thizz.alert(data);
			}
		}
	});
 },
 
 confirmContinueWithoutSaving: function (continuation) {
	if(!this.isSaved()) {
		mctracker.confirm("<div style='text-align: left;'><span style='font-weight: bold;'>Warning: Your work is not saved yet!</span><hr>Do you want to continue anyway?</div>", continuation, null, null, null, null, true);
	} else
		continuation();
 },

 /**
  * @method onNew
  */
 onNew: function() {
	
	 var thizz = this;
	 this.confirmContinueWithoutSaving(function () {
		 thizz.preventLayerChangedEvent = true;
			
		 thizz.layer.clear(); 
			
		 thizz.propertiesForm.clear(false); // false to tell inputEx to NOT send the updatedEvt

		 thizz.markSaved();

		 thizz.preventLayerChangedEvent = false;
	 });
	 
 },

 /**
  * @method onDelete
  */
 onDelete: function() {
	 var thizz = this;
	 mctracker.confirm("Are you sure you want to delete this message flow?", function () {
      mctracker.showProcessing();
      var value = thizz.getValue();
      thizz.adapter.deleteWiring({name: value.name, language: thizz.options.languageName},{
 			success: function(result) {
                if (result && result.error) {
                    mctracker.hideProcessing();
                    mctracker.alert("<div style='text-align: left;'><span style='font-weight: bold;'>Unable to delete wiring.</span><hr>Error:<br>" + mctracker.htmlEncode(result.error) + "</div>", null, null, null, true);
                } else {
                    loadMessageFlows();
                    thizz.onNew();
                    mctracker.hideProcessing("Deleted successfully!");
                }
 			},
			failure: function(errorStr) {
                mctracker.hideProcessing();
                mctracker.alert("Unable to delete wiring.<hr>Error: " + errorStr, null, null, null, true);
			},
			scope: thizz
 		});
       
    });
 },

 /**
  * @method onSave
  */
 onSave: function() {
    this.saveModule();
 },

 /**
  * @method renderLoadPanel
  */
 renderLoadPanel: function() {
    if( !this.loadPanel) {
       this.loadPanel = new widget.Panel('WiringEditor-loadPanel', {
          fixedcenter: true,
          draggable: true,
          width: '500px',
          visible: false,
          modal: true
       });
       this.loadPanel.setHeader("Select the message flow design to load");
       this.loadPanel.setBody("Filter: <input type='text' id='loadFilter' /><div id='loadPanelBody'></div>");
       this.loadPanel.render(document.body);

		// Listen the keyup event to filter the module list
		Event.onAvailable('loadFilter', function() {
			Event.addListener('loadFilter', "keyup", this.inputFilterTimer, this, true);
		}, this, true);

    }
 },

	/**
	 * Method called from each keyup on the search filter in load panel.
	 * The real filtering occurs only after 500ms so that the filter process isn't called too often
	 */
	inputFilterTimer: function() {
		if(this.inputFilterTimeout) {
			clearTimeout(this.inputFilterTimeout);
			this.inputFilterTimeout = null;
		}
		var that = this;
		this.inputFilterTimeout = setTimeout(function() {
				that.updateLoadPanelList(Dom.get('loadFilter').value);
		}, 500);
	},


 /**
  * @method updateLoadPanelList
  */
 updateLoadPanelList: function(filter) {
	
    var list = WireIt.cn("ul");
    if(lang.isArray(this.pipes)) {
       for(var i = 0 ; i < this.pipes.length ; i++) {
          var module = this.pipes[i];
          this.pipesByName[module.name] = module;
          if(!filter || filter === "" || module.name.match(new RegExp(filter,"i")) ) {
	          list.appendChild( WireIt.cn('li',null,{cursor: 'pointer'},module.name) );
			}
       }
    }
    var panelBody = Dom.get('loadPanelBody');
    panelBody.innerHTML = "";
    panelBody.appendChild(list);

    Event.addListener($("li",list), 'click', function(e,args) {
    	this.loadPipe($(Event.getTarget(e)).text());
    }, this, true);

 },

 /**
  * @method load
  */
 load: function() {
    
    this.adapter.listWirings({language: this.options.languageName},{
			success: function(result) {
				this.onLoadSuccess(result);
			},
			failure: function(errorStr) {
				this.alert("Unable to load the wirings: "+errorStr);
			},
			scope: this
		}
		);

 },

 /**
  * @method onLoadSuccess
  */
 onLoadSuccess: function(wirings) {
		this.pipes = wirings;
		this.pipesByName = {};
		
		this.renderLoadPanel();
    	this.updateLoadPanelList();

		if(!this.afterFirstRun) {
			var p = window.location.search.substr(1).split('&');
			var oP = {};
			for(var i = 0 ; i < p.length ; i++) {
				var v = p[i].split('=');
				oP[v[0]]=window.decodeURIComponent(v[1]);
			}
			this.afterFirstRun = true;
			if(oP.autoload) {
				this.loadPipe(oP.autoload);
				return;
			}
		}

    this.loadPanel.show();
	},

 /**
  * @method getPipeByName
  * @param {String} name Pipe's name
  * @return {Object} return the evaled json pipe configuration
  */
 getPipeByName: function(name) {
    var n = this.pipes.length,ret;
    for(var i = 0 ; i < n ; i++) {
       if(this.pipes[i].name == name) {
          // Try to eval working property:
          try {
             ret = JSON.parse(this.pipes[i].working);
             return ret;
          }
          catch(ex) {
             this.alert("Unable to eval working json for module "+name);
             return null;
          }
       }
    }
    
    return null;
 },
 
 /**
  * @method loadPipe
  * @param {String} name Pipe name
  */
 loadPipe: function(name) {
	 
	 var thizz = this;
	 
	 var doLoad = function () {
			try {
				
				thizz.preventLayerChangedEvent = true;
			
				thizz.loadPanel.hide();
			
		    var wiring = thizz.getPipeByName(name), i;

			 if(!wiring) {
				 thizz.alert("The wiring '"+name+"' was not found.");
				return;
		  	 }

			// Force wirings on screen
			jQuery.each(wiring.modules, function (i, module) {
				jQuery.each(module.config.position, function (j, coord) {
					if (coord < 0)
						module.config.position[j] = coord * -1;
				});
			});

		    // TODO: check if current wiring is saved...
			 thizz.layer.clear();
		    
			 thizz.propertiesForm.setValue(wiring.properties, false); // the false tells inputEx to NOT fire the updatedEvt
		    
		    if(lang.isArray(wiring.modules)) {
		      
		       // Containers
		       for(i = 0 ; i < wiring.modules.length ; i++) {
		          var m = wiring.modules[i];
		          if(thizz.modulesByName[m.name]) {
		             var baseContainerConfig = thizz.modulesByName[m.name].container;
		             YAHOO.lang.augmentObject(m.config, baseContainerConfig); 
		             m.config.title = m.name;
		             var container = thizz.layer.addContainer(m.config);
		             Dom.addClass(container.el, "WiringEditor-module-"+m.name);
		             container.setValue(m.value);
		          }
		          else {
		             throw new Error("WiringEditor: module '"+m.name+"' not found !");
		          }
		       }
		       
		       // Wires
		       if(lang.isArray(wiring.wires)) {
		           for(i = 0 ; i < wiring.wires.length ; i++) {
		              // On doit chercher dans la liste des terminaux de chacun des modules l'index des terminaux...
		        	   thizz.layer.addWire(wiring.wires[i]);
		           }
		        }
		     }
		     
		    thizz.markSaved();
			
		    thizz.preventLayerChangedEvent = false;
			
		  	}
		  	catch(ex) {
		  		thizz.alert(ex);
		  	}
		};
		
	this.confirmContinueWithoutSaving(doLoad);

 },

 	renderAlertPanel: function() {
		
 	 /**
     * @property alertPanel
     * @type {YAHOO.widget.Panel}
     */
		this.alertPanel = new widget.Panel('WiringEditor-alertPanel', {
         fixedcenter: true,
         draggable: true,
         width: '500px',
         visible: false,
         modal: true
      });
      this.alertPanel.setHeader("Message");
      this.alertPanel.setBody("<div id='alertPanelBody'></div><button id='alertPanelButton'>Ok</button>");
      this.alertPanel.render(document.body);
		Event.addListener('alertPanelButton','click', function() {
			this.alertPanel.hide();
		}, this, true);
	},

	onLayerChanged: function() {
		if(!this.preventLayerChangedEvent) {
			this.markUnsaved();
		}
	},

	markSaved: function() {
		this.savedStatusEl.style.display = 'none';
	},
	
	markUnsaved: function() {
		this.savedStatusEl.style.display = '';
	},

	isSaved: function() {
		return (this.savedStatusEl.style.display == 'none');
	},
 
 /**
  * This method return a wiring within the given vocabulary described by the modules list
  * @method getValue
  */
 getValue: function() {
    
   var i;
   var obj = {modules: [], wires: [], properties: null};

   for( i = 0 ; i < this.layer.containers.length ; i++) {
      obj.modules.push( {name: this.layer.containers[i].options.title, value: this.layer.containers[i].getValue(), config: this.layer.containers[i].getConfig()});
   }

   for( i = 0 ; i < this.layer.wires.length ; i++) {
      var wire = this.layer.wires[i];

      var wireObj = { 
         src: {moduleId: WireIt.indexOf(wire.terminal1.container, this.layer.containers), terminal: wire.terminal1.options.name}, 
         tgt: {moduleId: WireIt.indexOf(wire.terminal2.container, this.layer.containers), terminal: wire.terminal2.options.name}
      };
      obj.wires.push(wireObj);
   }
   
   obj.properties = this.propertiesForm.getValue();
    
   return {
      name: obj.properties.name,
      working: obj
   };
 }


};


/**
 * WiringEditor Adapters
 * @static
 */
WireIt.WiringEditor.adapters = {};


})();
   
