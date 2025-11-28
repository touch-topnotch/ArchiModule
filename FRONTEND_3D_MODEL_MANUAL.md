# 🚀 Hitem3D API Integration Guide for Frontend

## 📋 **Overview**

This guide explains how to integrate Hitem3D 3D model generation API into the frontend application. The API allows users to generate 3D models from single images or multi-view images (front, back, left, right).

## 🏗️ **Architecture**

```

Frontend → Master Server (8001) → skvis Server (8320) → Hitem3D API

```

-**Frontend** sends requests to Master Server

-**Master Server** handles authentication and forwards to skvis

-**skvis Server** processes images and calls Hitem3D API

-**Hitem3D API** generates 3D models

## 🔧 **API Endpoints**

### **Base URL**

```

http://89.169.36.93:8001/tools/v1/hitem3d

```

### **1. Submit Images** - `POST /submit-images`

**Purpose:** Submit images for 3D model generation

**Authentication:** Bearer Token required

**Request Body:**

```typescript

interfaceHitem3DSubmitRequest {

// Single image mode

  other?:string;


// Multi-image mode (order matters!)

  front?:string;    // Front view

  back?:string;     // Back view  

  left?:string;     // Left view

  right?:string;    // Right view


// API parameters

  request_type?:number;    // Default: 3

  model?:string;           // Default: "hitem3dv1.5"

  resolution?:string;      // Optional

  face?:number;           // Optional

  format?:number;         // 1=obj, 2=glb, 3=stl, 4=fbx (Default: 2)

  callback_url?:string;   // Optional

}

```

**Response:**

```typescript

interfaceHitem3DTaskId {

  task_id:string;

}

```

### **2. Get Result** - `GET /get-object`

**Purpose:** Get generation status and result

**Authentication:** Bearer Token required

**Query Parameters:**

-`task_id` (required) - Task ID from submit response

-`legacy` (optional) - Return legacy format (default: false)

**Response (New Format):**

```typescript

interfaceHitem3DQueryResult {

  task_id:string;

  state:'created'|'queueing'|'processing'|'success'|'failed';

  id?:string;

  url?:string;          // Download URL for 3D model

  cover_url?:string;   // Preview image URL

  message?:string;     // Error message if failed

}

```

**Response (Legacy Format):**

```typescript

interfaceLegacyResult {

  progress:number;     // Progress percentage (0-100)

  object?: {

    glb_url:string;

    fbx_url:string;

    usdz_url:string;

    obj_url:string;

  };

  texture?:null;

}

```

## 💻 **Implementation Examples**

### **1. TypeScript Service Class**

```typescript

classHitem3DService {

private baseUrl ='http://89.169.36.93:8001/tools/v1/hitem3d';

private token:string;


constructor(token:string) {

this.token=token;

  }


/**

   * Submit images for 3D model generation

   */

asyncsubmitImages(request:Hitem3DSubmitRequest):Promise<string> {

constresponse=awaitfetch(`${this.baseUrl}/submit-images`, {

      method: 'POST',

      headers: {

'Content-Type': 'application/json',

'Authorization': `Bearer ${this.token}`

      },

      body: JSON.stringify(request)

    });


if (!response.ok) {

consterror=awaitresponse.text();

thrownewError(`Submit failed: ${error}`);

    }


constresult:Hitem3DTaskId=awaitresponse.json();

returnresult.task_id;

  }


/**

   * Get generation result

   */

asyncgetResult(taskId:string, legacy =false):Promise<any> {

constresponse=awaitfetch(

`${this.baseUrl}/get-object?task_id=${taskId}&legacy=${legacy}`,

      {

        headers: {

'Authorization': `Bearer ${this.token}`

        }

      }

    );


if (!response.ok) {

consterror=awaitresponse.text();

thrownewError(`Get result failed: ${error}`);

    }


returnawaitresponse.json();

  }


/**

   * Poll for result with progress updates

   */

asyncpollResult(

    taskId:string,

onProgress?: (progress:number) =>void,

onStateChange?: (state:string) =>void

  ):Promise<any> {

returnnewPromise((resolve, reject) => {

constpoll=async () => {

try {

constresult=awaitthis.getResult(taskId, true); // Use legacy for progress


if (onProgress) {

onProgress(result.progress);

          }


if (onStateChange) {

onStateChange(result.state);

          }


if (result.state==='success') {

resolve(result);

          } elseif (result.state==='failed') {

reject(newError(result.message||'Generation failed'));

          } else {

// Continue polling every 2 seconds

setTimeout(poll, 2000);

          }

        } catch (error) {

reject(error);

        }

      };


poll();

    });

  }

}

```

### **2. React Hook**

```typescript

import { useState, useCallback } from'react';


interfaceUseHitem3DReturn {

submitImages: (request:Hitem3DSubmitRequest) =>Promise<void>;

  result:any|null;

  progress:number;

  state:string;

  loading:boolean;

  error:string|null;

}


exportconstuseHitem3D= (token:string):UseHitem3DReturn=> {

const [result, setResult] =useState<any|null>(null);

const [progress, setProgress] =useState(0);

const [state, setState] =useState<string>('');

const [loading, setLoading] =useState(false);

const [error, setError] =useState<string|null>(null);


constservice=newHitem3DService(token);


constsubmitImages=useCallback(async (request:Hitem3DSubmitRequest) => {

setLoading(true);

setError(null);

setProgress(0);

setState('');

setResult(null);


try {

consttaskId=awaitservice.submitImages(request);


constfinalResult=awaitservice.pollResult(

taskId,

        (progress) =>setProgress(progress),

        (state) =>setState(state)

      );


setResult(finalResult);

    } catch (err) {

setError(errinstanceofError?err.message:'Unknown error');

    } finally {

setLoading(false);

    }

  }, [service]);


return {

submitImages,

result,

progress,

state,

loading,

error

  };

};

```

### **3. React Component**

```tsx

importReact, { useState } from'react';

import { useHitem3D } from'./useHitem3D';


interfaceHitem3DGeneratorProps {

  token:string;

}


constHitem3DGenerator:React.FC<Hitem3DGeneratorProps> = ({ token }) => {

const [selectedFiles, setSelectedFiles] =useState<File[]>([]);

const [mode, setMode] =useState<'single'|'multi'>('single');

const [imagePaths, setImagePaths] =useState<{

    front?:string;

    back?:string;

    left?:string;

    right?:string;

    other?:string;

  }>({});


const { submitImages, result, progress, state, loading, error } =useHitem3D(token);


consthandleFileUpload= (event:React.ChangeEvent<HTMLInputElement>) => {

constfiles=Array.from(event.target.files|| []);

setSelectedFiles(files);


// Convert files to paths (you'll need to implement file upload logic)

if (mode==='single'&&files.length >0) {

setImagePaths({ other: `/uploads/${files[0].name}` });

    } elseif (mode==='multi'&&files.length >=4) {

setImagePaths({

        front: `/uploads/${files[0].name}`,

        back: `/uploads/${files[1].name}`,

        left: `/uploads/${files[2].name}`,

        right: `/uploads/${files[3].name}`

      });

    }

  };


consthandleSubmit=async () => {

if (Object.keys(imagePaths).length ===0) return;


awaitsubmitImages({

...imagePaths,

      model: 'hitem3dv1.5',

      format: 2, // GLB format

      request_type: 3

    });

  };


constgetStateColor= (state:string) => {

switch (state) {

case'created': return'blue';

case'queueing': return'orange';

case'processing': return'yellow';

case'success': return'green';

case'failed': return'red';

default: return'gray';

    }

  };


return (

<divclassName="hitem3d-generator">

<h2>🎯 Hitem3D 3D Model Generator</h2>


{/* Mode Selection */}

<divclassName="mode-selection">

<label>

<input

type="radio"

value="single"

checked={mode==='single'}

onChange={(e) =>setMode(e.target.valueas'single')}

/>

          Single Image

</label>

<label>

<input

type="radio"

value="multi"

checked={mode==='multi'}

onChange={(e) =>setMode(e.target.valueas'multi')}

/>

          Multi-View (Front, Back, Left, Right)

</label>

</div>


{/* File Upload */}

<divclassName="file-upload">

<input

type="file"

multiple={mode==='multi'}

onChange={handleFileUpload}

accept="image/*"

disabled={loading}

/>

{mode==='multi'&& (

<pclassName="help-text">

            Upload 4 images in order: Front, Back, Left, Right

</p>

        )}

</div>


{/* Submit Button */}

<button

onClick={handleSubmit}

disabled={loading||Object.keys(imagePaths).length ===0}

className="submit-btn"

>

{loading?'Generating...':'Generate 3D Model'}

</button>


{/* Progress Display */}

{loading&& (

<divclassName="progress-section">

<divclassName="progress-info">

<span>State: </span>

<spanstyle={{ color: getStateColor(state) }}>

{state.toUpperCase()}

</span>

</div>

<divclassName="progress-bar">

<div

className="progress-fill"

style={{ width: `${progress}%` }}

/>

</div>

<divclassName="progress-text">{progress}%</div>

</div>

      )}


{/* Error Display */}

{error&& (

<divclassName="error-message">

          ❌ Error: {error}

</div>

      )}


{/* Result Display */}

{result&&result.state==='success'&& (

<divclassName="result-section">

<h3>✅ Generation Complete!</h3>

{result.object?.glb_url&& (

<divclassName="download-links">

<a

href={result.object.glb_url}

download

className="download-btn"

>

                📥 Download GLB Model

</a>

{result.object.fbx_url&& (

<a

href={result.object.fbx_url}

download

className="download-btn"

>

                  📥 Download FBX Model

</a>

              )}

</div>

          )}

{result.cover_url&& (

<divclassName="preview">

<img

src={result.cover_url}

alt="3D Model Preview"

className="preview-image"

/>

</div>

          )}

</div>

      )}

</div>

  );

};


exportdefaultHitem3DGenerator;

```

### **4. CSS Styles**

```css

.hitem3d-generator {

max-width: 600px;

margin: 0 auto;

padding: 20px;

font-family: Arial, sans-serif;

}


.mode-selection {

margin: 20px0;

}


.mode-selectionlabel {

margin-right: 20px;

cursor: pointer;

}


.file-upload {

margin: 20px0;

}


.help-text {

font-size: 12px;

color: #666;

margin-top: 5px;

}


.submit-btn {

background: #007bff;

color: white;

border: none;

padding: 12px24px;

border-radius: 6px;

cursor: pointer;

font-size: 16px;

}


.submit-btn:disabled {

background: #ccc;

cursor: not-allowed;

}


.progress-section {

margin: 20px0;

padding: 15px;

background: #f8f9fa;

border-radius: 6px;

}


.progress-info {

margin-bottom: 10px;

font-weight: bold;

}


.progress-bar {

width: 100%;

height: 20px;

background: #e9ecef;

border-radius: 10px;

overflow: hidden;

}


.progress-fill {

height: 100%;

background: linear-gradient(90deg, #28a745, #20c997);

transition: width 0.3s ease;

}


.progress-text {

text-align: center;

margin-top: 5px;

font-weight: bold;

}


.error-message {

background: #f8d7da;

color: #721c24;

padding: 10px;

border-radius: 6px;

margin: 10px0;

}


.result-section {

margin: 20px0;

padding: 15px;

background: #d4edda;

border-radius: 6px;

}


.download-links {

margin: 10px0;

}


.download-btn {

display: inline-block;

background: #28a745;

color: white;

text-decoration: none;

padding: 8px16px;

border-radius: 4px;

margin-right: 10px;

margin-bottom: 10px;

}


.download-btn:hover {

background: #218838;

}


.preview {

margin-top: 15px;

}


.preview-image {

max-width: 200px;

border-radius: 6px;

}

```

## 🎯 **Task States & Progress**

| State | Description | Progress | Color |

|-------|-------------|----------|-------|

| `created` | Task created | 5% | Blue |

| `queueing` | In queue | 20% | Orange |

| `processing` | Generating | 60% | Yellow |

| `success` | Complete | 100% | Green |

| `failed` | Error | 0% | Red |

## 📁 **File Formats**

| Code | Format | Use Case |

|------|--------|----------|

| 1 | OBJ | Standard 3D modeling |

| 2 | GLB | **Recommended** - Web, AR/VR |

| 3 | STL | 3D printing |

| 4 | FBX | Game engines, 3D software |

## ⚠️ **Important Notes**

1.**Authentication Required** - All requests need Bearer Token

2.**File Paths** - Pass server file paths, not client files

3.**Multi-Image Order** - Front → Back → Left → Right

4.**URL Expiry** - Download URLs valid for ~1 hour

5.**Progress Tracking** - Use legacy format for progress percentage

6.**Error Handling** - Always check response status and handle errors

## 🔗 **Testing**

Use these endpoints for testing:

-**API Docs:**`http://89.169.36.93:8001/docs`

-**Swagger UI:**`http://89.169.36.93:8001/docs#/default`

-**Health Check:**`http://89.169.36.93:8001/`

## 🚀 **Quick Start**

1.**Get Authentication Token** from your auth system

2.**Create Hitem3DService instance** with token

3.**Upload files** to server and get paths

4.**Submit images** using `submitImages()`

5.**Poll for results** using `pollResult()`

6.**Display progress** and final result

This integration provides a complete 3D model generation workflow for your frontend application! 🎉
