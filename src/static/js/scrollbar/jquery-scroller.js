/************************************************************************************
 
jQuery Horizontal and Vertical Scroller

Author: http://www.theninjaofweb.com/tools/

Free for personal use! 

For commercial use you need to purchase this script! For example if you sell it as a
part of a package or website, implement it for a client’s website, etc.

************************************************************************************/

(function($) {

	$.fn.Scroller = function() {	
		var args = arguments[0] || {};    
		direction = args.direction; //horizontal or vertical 
		speed = args.speed; //scrolling speed, 1-10, 1: fastest
		var v_button = args.show_v_button;
		
		if(!direction){
			direction = 'vertical';
		}
		if(!speed){
			speed = 5;
		}
		
		if(direction == 'vertical'){
		    var up_arrow = '/static/images/site/scroll/arrow-up.png';
		    var up_arrow_hold = '/static/images/site/scroll/arrow-up-hold.png';
		    var down_arrow = '/static/images/site/scroll/arrow-down.png';
		    var down_arrow_hold = '/static/images/site/scroll/arrow-down-hold.png';
			var scroller = '/static/images/site/scroll/scroller-v-button.png';
			var scroller_hold = '/static/images/site/scroll/scroller-v-button-hold.png';			
		}
		else if(direction == 'horizontal'){			
			var left_arrow = '/static/images/site/scroll/arrow-left.png';
			var left_arrow_hold = '/static/images/site/scroll/arrow-left-hold.png';
			var right_arrow = '/static/images/site/scroll/arrow-right.png';
			var right_arrow_hold = '/static/images/site/scroll/arrow-right-hold.png';
			var scroller = '/static/images/site/scroll/scroller-h-button.png';
			var scroller_hold = '/static/images/site/scroll/scroller-h-button-hold.png';			
		}
		
		speed = speed * 20;
		speed_val = speed;
		
		var this_idname = $(this).attr('id');
				
		$(this).css('overflow','hidden');
		
		var boxwidth = $(this).width();
		var boxheight = $(this).height();	

		//get content
		var boxcontent = $(this).html();	
		$(this).html('');
		

		//vertical scroller
		if(direction == 'vertical'){								
			
			
			//put content into an inside div			
			$(this).append('<div class="scroller-content">'+boxcontent+'</div><div class="scroller-control">'+
			'<div class="scroller-up"><a href="#"><img src="'+up_arrow+'" /></a></div><div class="scroller-field"></div><div class="scroller-down"><a href="#"><img src="'+down_arrow+'" /></a></div>'+
			'</div>');
			var boxwidth = $(this).width();
			var boxheight = $(this).height();	
			var nuwidth = boxwidth - 40;
			$('.scroller-content',this).css('width',nuwidth+'px');
			
					
			$('.scroller-control',this).click(function(event){
			event.preventDefault();
			})
					
			//set scroller field
			arrowheights = $('.scroller-up',this).height();		
			arrowheights = arrowheights + $('.scroller-down',this).height() + 20;
			nuboxheight = boxheight - arrowheights;
			$('.scroller-field',this).css('height',nuboxheight);
			
			
			
			var content_h = $('.scroller-content',this).height();
			
			//1px move w scroller = ? px move in content  --> content height / scroller available moving field		
			var stepping = ((content_h-boxheight) / max);		
			
			var timeout = '0';
			
			//append scroll button
			if (v_button) {
				scroller =  $('<div class="scroller"><img src="'+scroller+'" /></div>');
			} else {
				scroller =  $('<div class="scroller"></div>');
			}

			$('.scroller-field',this).append(scroller);

			var scroller_field_h = $('.scroller-field',this).height();
			
			//define max position of scroller			
			var max = scroller_field_h - $('.scroller',this).height();			

			//scroll up
			var scrollUp = function(this_id,hide_hold){					
				var currtop = $('#'+this_id+' .scroller-content').css('top');		
										
				currtop = parseInt(currtop);
				
					if(currtop <= 0){
						if(hide_hold != true){
							$('#'+this_id+' .scroller-up a img').attr('src',up_arrow_hold);		
						}								
						
						currtop = currtop + 10;
						if(currtop > 0){currtop = 0;}
						$('#'+this_id+' .scroller-content').css('top',currtop+'px');
					
						//set scrollbar position also										
						var scurry = Math.round(currtop / stepping) * -1;
						$('#'+this_id+' .scroller').css('top',scurry+'px');						
					}
			};
			
			var speedval = speed;
			$('.scroller-up',this).mousedown(function(){				
				timeout = setInterval(function(){scrollUp(this_idname);},speedval);
				return false;
			});
			$('.scroller-up',this).mouseout(function(){			
				if(timeout){
					clearInterval(timeout);				
					$('a img',this).attr('src',up_arrow);				
				}
				return false;
			});
			$('.scroller-up',this).mouseup(function(){			
				if(timeout){
					clearInterval(timeout);
					$('a img',this).attr('src',up_arrow);
				}
				return false;
			});

			
			//scroll down to bottom		
			var scrollDown = function(this_id,hide_hold){ 
					var inboxheight = $('#'+this_id+' .scroller-content').height() - boxheight;			
					var currtop = $('#'+this_id+' .scroller-content').css('top');
					currtop = Number(currtop.replace('px',''));
					if(inboxheight >= (currtop * -1))
					{			
						if(hide_hold != true){
							$('#'+this_id+' .scroller-down a img').attr('src',down_arrow_hold);
						}
						
						currtop = currtop - 10;
						$('#'+this_id+' .scroller-content').css('top',currtop+'px');
						
						//set scrollbar position also						
						var scurry = Math.round(currtop / stepping) * -1;
						$('#'+this_id+' .scroller').css('top',scurry+'px');						
					}	
			};
			
			
			$('.scroller-down',this).mousedown(function(){

				timeout = setInterval(function(){scrollDown(this_idname);}, speedval);
				return false;
			});
			$('.scroller-down',this).mouseout(function(){
				if(timeout){
					clearInterval(timeout);
					$('.scroller-down a img').attr('src',down_arrow);
				}
				return false;
			});
			$('.scroller-down',this).mouseup(function(){
				if(timeout){
					clearInterval(timeout);
					$('.scroller-down a img').attr('src',down_arrow);
				}
				return false;
			});
			
			
			
			
			
			//make scrollbutton draggable
			var dragIt = function(element,this_id){			
				var dragok = false;
				var y,el,ely,nuy;			
			
				function move(e){
					if (!e) e = window.event;
					if (dragok){
						nuy = ely + e.clientY - y;							
						if(nuy >= 0 && nuy <= max){
							numy = nuy;
							nuy = nuy + "px";	
							el.css('top',nuy);			

							//position content also with the stepping value
							$('#'+this_id+' .scroller-content').css('top',Math.round(stepping * numy * -1)+'px');
							
							
						}
						return false;
					}
				}

				function down(e){
					if (!e) e = window.event;			
					dragok = true;			 
					el = element;			 
					ely = parseInt(element.css('top')+0);			 
					y = e.clientY;
					$(document).mousemove(move);		
					$('img',el).attr('src',scroller_hold);
					return false;
				}
				

				function up(){
					dragok = false;				
					element.mousemove(null);
					$('img',element).attr('src',scroller);
				}

				element.mousedown(down);
				$(document).mouseup(up);						
				
			}		
			dragIt( $('.scroller',this), this_idname );
			
			
			//add mouse wheel scrolling
			moveObject = function(event){		
				if (!event) event = window.event;  

				if (event.wheelDelta || event.detail){
					var value = event.wheelDelta;
					if(!value){value = event.detail;}
					if(value < 0){
						if($.browser.mozilla){
						scrollUp(this_idname,true);
						}else{
						scrollDown(this_idname,true);							
						}
					}
					else{
						if($.browser.mozilla){							
						scrollDown(this_idname,true);
						}else{
						scrollUp(this_idname,true);
						}
					}
				}
			}		
			
			var element = document.getElementById(this_idname);
			if(window.addEventListener){
				element.addEventListener('DOMMouseScroll', moveObject, false);
			}
			element.onmousewheel = moveObject;			

			var thizz = this;

			var updateScroller = function () {
				//check if content is long enough to use scroller
				if(content_h > boxheight){			
					//set opacity of scroller
					$('.scroller-control',thizz).show();
				}else{
					//set opacity of scroller
					$('.scroller-control',thizz).hide();
				}
			};
			updateScroller();
			
			$('.scroller-content',this).resize(function (){
				content_h = $('.scroller-content',thizz).height();
				boxheight = thizz.height();
				stepping = ((content_h-boxheight) / max);
				max = scroller_field_h - $('.scroller',thizz).height();
				boxwidth = thizz.width();
				boxheight = thizz.height();	
				nuwidth = boxwidth - 40;
				$('.scroller-content',thizz).css('width',nuwidth+'px');

				updateScroller();
			});
			
		}
		else if(direction == 'horizontal'){
			
			
			//put content into an inside div			
			$(this).append('<div class="h-scroller-content">'+boxcontent+'</div><div class="h-scroller-control">'+
			'<div class="h-scroller-left"><a href="#"><img src="'+left_arrow+'" /></a></div><div class="h-scroller-field"></div><div class="h-scroller-right"><a href="#"><img src="'+right_arrow+'" /></a></div>'+
			'</div>');		
			var nuheight = boxheight - 40;
			$('.h-scroller-content',this).css('height',nuheight+'px');
			
			$('.h-scroller-control',this).click(function(event){
			event.preventDefault();
			})
			
			
			//set scroller field
			arrowwidths = $('.h-scroller-left',this).width();		
			arrowwidths = arrowwidths + $('.h-scroller-right',this).width() + 20;
			nuboxwidth = boxwidth - arrowwidths;
			$('.h-scroller-field',this).css('width',nuboxwidth);
			
			
			var content_w = $('.h-scroller-content',this).children().width();
			
			
			//check if content is long enough to use scroller
			if(content_w > boxwidth){			
				
				//append scroll button
				$('.h-scroller-field',this).append('<div class="h-scroller"><img src="'+scroller+'" /></div>');
				
				
				var scroller_field_w = $('.h-scroller-field',this).width();
				
				//define max position of scroller			
				var max = scroller_field_w - $('.h-scroller',this).width();			
				
				//1px move w scroller = ? px move in content  --> content height / scroller available moving field		
				var stepping = ((content_w-boxwidth) / max);		
					
														
				//scroll right
				var scrollRight = function(this_id,hide_hold){ 					
						var inboxwidth = $('#'+this_id+' .h-scroller-content').children().width() - boxwidth;								
						var currleft = $('#'+this_id+' .h-scroller-content').css('left');
						currleft = Number(currleft.replace('px',''));
						if(inboxwidth >= (currleft * -1))
						{			
							if(hide_hold != true){
								$('#'+this_id+' .h-scroller-right a img').attr('src',right_arrow_hold);
							}
							
							currleft = currleft - 10;
							$('#'+this_id+' .h-scroller-content').css('left',currleft+'px');
							
							//set scrollbar position also						
							var scurry = Math.round(currleft / stepping) * -1;
							$('#'+this_id+' .h-scroller').css('left',scurry+'px');						
						}	
				};
				
				
				$('.h-scroller-right',this).mousedown(function(){

					timeout = setInterval(function(){scrollRight(this_idname);}, speedval);
					return false;
				});
				$('.h-scroller-right',this).mouseout(function(){
					if(timeout){
						clearInterval(timeout);
						$('.h-scroller-right a img').attr('src',right_arrow);
					}
					return false;
				});
				$('.h-scroller-right',this).mouseup(function(){
					if(timeout){
						clearInterval(timeout);
						$('.h-scroller-right a img').attr('src',right_arrow);
					}
					return false;
				});
					
					
														
				//scroll left
				var scrollLeft = function(this_id,hide_hold){ 					
						var inboxwidth = $('#'+this_id+' .h-scroller-content').children().width() - boxwidth;								
						var currleft = $('#'+this_id+' .h-scroller-content').css('left');
						currleft = Number(currleft.replace('px',''));
						if(currleft <= 0)						
						{			
							if(hide_hold != true){
								$('#'+this_id+' .h-scroller-left a img').attr('src',left_arrow_hold);
							}
							
							currleft = currleft + 10;
							if(currleft > 0){currleft = 0;}
							$('#'+this_id+' .h-scroller-content').css('left',currleft+'px');
							
							//set scrollbar position also						
							var scurry = Math.round(currleft / stepping) * -1;
							$('#'+this_id+' .h-scroller').css('left',scurry+'px');						
						}	
												
				};
				
				
				$('.h-scroller-left',this).mousedown(function(){

					timeout = setInterval(function(){scrollLeft(this_idname);}, speedval);
					return false;					
				});
				$('.h-scroller-left',this).mouseout(function(){
					if(timeout){
						clearInterval(timeout);
						$('.h-scroller-left a img').attr('src',left_arrow);
					}
					return false;
				});
				$('.h-scroller-left',this).mouseup(function(){
					if(timeout){
						clearInterval(timeout);
						$('.h-scroller-left a img').attr('src',left_arrow);
					}
					return false;
				});					
					
					
					
				//make scrollbutton draggable
				var dragIt = function(element,this_id){			
					var dragok = false;
					var x,el,elx,nux;			
				
					function move(e){
						if (!e) e = window.event;
						if (dragok){
							nux = elx + e.clientX - x;							
							if(nux >= 0 && nux <= max){
								numx = nux;
								nux = nux + "px";	
								el.css('left',nux);			

								//position content also with the stepping value
								$('#'+this_id+' .h-scroller-content').css('left',Math.round(stepping * numx * -1)+'px');
								
								
							}
							return false;
						}
					}

					function down(e){
						if (!e) e = window.event;			
						dragok = true;			 
						el = element;			 
						elx = parseInt(element.css('left')+0);			 
						x = e.clientX;
						$(document).mousemove(move);		
						$('img',el).attr('src',scroller_hold);
						return false;
					}
					

					function up(){
						dragok = false;				
						element.mousemove(null);
						$('img',element).attr('src',scroller);
					}

					element.mousedown(down);
					$(document).mouseup(up);						
					
				}		
				dragIt( $('.h-scroller',this), this_idname );	
				
				
				
				//add mouse wheel scrolling
				moveObject = function(event){		
					if (!event) event = window.event;  

					if (event.wheelDelta || event.detail){
						var value = event.wheelDelta;
						if(!value){value = event.detail;}
						if(value < 0){
							if($.browser.mozilla){
							scrollLeft(this_idname,true);
							}else{
							scrollRight(this_idname,true);							
							}
						}
						else{
							if($.browser.mozilla){
							scrollRight(this_idname,true);
							}else{
							scrollLeft(this_idname,true);							
							}
						}
					}
				}		
				
				var element = document.getElementById(this_idname);
				if(window.addEventListener){
					element.addEventListener('DOMMouseScroll', moveObject, false);
				}
				element.onmousewheel = moveObject;
				
				
					
			}
			else{
				//set opacity of scroller
				$('.h-scroller-control',this).css({ opacity: 0.3 });			
			}
			
		}
	
	
	}

})(jQuery);


