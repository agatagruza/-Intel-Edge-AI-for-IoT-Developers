
import numpy as np
import time
from openvino.inference_engine import IENetwork, IECore
import os
import cv2
import argparse
import sys


class Queue:
    '''
    Class for dealing with queues
    '''
    def __init__(self):
        self.queues=[]

    def add_queue(self, points):
        self.queues.append(points)

    def get_queues(self, image):
        for q in self.queues:
            x_min, y_min, x_max, y_max=q
            frame=image[y_min:y_max, x_min:x_max]
            yield frame
    
    def check_coords(self, coords):
        d={k+1:0 for k in range(len(self.queues))}
        for coord in coords:
            for i, q in enumerate(self.queues):
                if coord[0]>q[0] and coord[2]<q[2]:
                    d[i+1]+=1
        return d


class PersonDetect:
    '''
    Class for the Person Detection Model.
    '''

    def __init__(self, model_name, device, threshold=0.60):
        self.model_weights=model_name+'.bin'
        self.model_structure=model_name+'.xml'
        self.device=device
        self.threshold=threshold

        try:
            self.model=IENetwork(self.model_structure, self.model_weights)
        except Exception as e:
            raise ValueError("Could not Initialise the network. Have you enterred the correct model path?")

        self.input_name=next(iter(self.model.inputs))
        self.input_shape=self.model.inputs[self.input_name].shape
        self.output_name=next(iter(self.model.outputs))
        self.output_shape=self.model.outputs[self.output_name].shape
        
    def box_shape(self, w, h):
        self.w = w
        self.h = h

    def load_model(self):
        #TODO: This method needs to be completed by you
        self.core = IECore()
        self.net = self.core.load_network(network=self.model, device_name=self.device, num_requests=1)
        #raise NotImplementedError
        
    def predict(self, image):
        #TODO: This method needs to be completed by you
        curr_image = self.preprocess_input(image)
        #print(curr_image)
        outputs = self.net.infer({self.input_name: curr_image})
        #print(outputs)
        coords = self.preprocess_outputs(outputs[self.output_name])
        #print(coords)
        self.draw_outputs(coords, image)
        return coords, image
        #raise NotImplementedError
    
    def draw_outputs(self, coords, image):
        #TODO: This method needs to be completed by you
        for pair in coords:
            cv2.rectangle(image, (pair[0], pair[1]), (pair[2], pair[3]), (0, 255, 0), 1)
        #raise NotImplementedError

    def preprocess_outputs(self, outputs):
        #TODO: This method needs to be completed by you
        coords_list = []
        for box in outputs[0][0]:
            conf = box[2]
            if conf >= self.threshold:
                #xmin, ymin, xmax, ymax = box[3], box[4], box[5], box[6]
                xmin, ymin, xmax, ymax = int(box[3] * self.w), int(box[4] * self.h), int(box[5] * self.w), int(box[6] * self.h)
                coords_list.append((xmin, ymin, xmax, ymax))
                
        return coords_list

#         coords_list = []
#         for box in outputs[0][0]:
#             conf = box[2]
#             # caval -> Confidence value
#             if conf >= self.threshold:
#                 xmin = int(box[3] * self.w)
#                 ymin = int(box[4] * self.h)
#                 xmax = int(box[5] * self.w)
#                 ymax = int(box[6] * self.h)
#                 coords_list.append((xmin, ymin, xmax, ymax))
#         return coords_list
    
    
        #raise NotImplementedError

    def preprocess_input(self, image):
        #TODO: This method needs to be completed by you
        curr_image = cv2.resize(image, (self.input_shape[3], self.input_shape[2]))
        # Change image from HWC to CHW
        curr_image = curr_image.transpose((2,0,1))
        curr_image = curr_image.reshape(1, *curr_image.shape)
        return curr_image
        #raise NotImplementedError

def main(args):
    model=args.model
    device=args.device
    video_file=args.video
    max_people=args.max_people
    threshold=args.threshold
    output_path=args.output_path

    start_model_load_time=time.time()
    pd= PersonDetect(model, device, threshold)
    pd.load_model()
    total_model_load_time = time.time() - start_model_load_time

    queue=Queue()
    
    try:
        queue_param=np.load(args.queue_param)
        for q in queue_param:
            queue.add_queue(q)
    except:
        print("error loading queue param file")

    try:
        cap=cv2.VideoCapture(video_file)
    except FileNotFoundError:
        print("Cannot locate video file: "+ video_file)
    except Exception as e:
        print("Something else went wrong with the video file: ", e)
    
    initial_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    initial_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_len = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    out_video = cv2.VideoWriter(os.path.join(output_path, 'output_video.mp4'), cv2.VideoWriter_fourcc(*'avc1'), fps, (initial_w, initial_h), True)
    
    counter=0
    start_inference_time=time.time()

    try:
        pd.box_shape(initial_w, initial_h)
        while cap.isOpened():
            ret, frame=cap.read()
            if not ret:
                break
            counter+=1
            
            coords, image= pd.predict(frame)
            num_people= queue.check_coords(coords)
            print(f"Total People in frame = {len(coords)}")
            print(f"Number of people in queue = {num_people}")
            out_text=""
            y_pixel=25
            
            for k, v in num_people.items():
                out_text += f"No. of People in Queue {k} is {v} "
                if v >= int(max_people):
                    out_text += f" Queue full; Please move to next Queue "
                cv2.putText(image, out_text, (15, y_pixel), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)
                out_text=""
                y_pixel+=40
            out_video.write(image)
            
        total_time=time.time()-start_inference_time
        total_inference_time=round(total_time, 1)
        fps=counter/total_inference_time

        with open(os.path.join(output_path, 'stats.txt'), 'w') as f:
            f.write(str(total_inference_time)+'\n')
            f.write(str(fps)+'\n')
            f.write(str(total_model_load_time)+'\n')

        cap.release()
        cv2.destroyAllWindows()
    except Exception as e:
        print("Could not run Inference: ", e)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--device', default='CPU')
    parser.add_argument('--video', default=None)
    parser.add_argument('--queue_param', default=None)
    parser.add_argument('--output_path', default='/results')
    parser.add_argument('--max_people', default=2)
    parser.add_argument('--threshold', default=0.60)
    
    args=parser.parse_args()

    main(args)