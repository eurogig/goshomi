import type {ReactFlowInstance} from '@xyflow/react';

/** Keep an off-screen tour component visible without changing the user's zoom. */
export function followTourNode(flow: ReactFlowInstance, active: string, bounds: {width:number;height:number}) {
 const target=flow.getInternalNode(active);
 const width=target?.measured?.width, height=target?.measured?.height;
 if(!target||!width||!height)return;
 const viewport=flow.getViewport(), position=target.internals.positionAbsolute;
 const left=position.x*viewport.zoom+viewport.x, top=position.y*viewport.zoom+viewport.y;
 const right=left+width*viewport.zoom, bottom=top+height*viewport.zoom;
 // Leave room for the floating map header and controls when judging visibility.
 const margin=24, header=Math.min(90,bounds.height/3);
 if(left<margin||right>bounds.width-margin||top<header||bottom>bounds.height-margin){
  void flow.setCenter(position.x+width/2,position.y+height/2,{zoom:viewport.zoom,duration:250});
 }
}
