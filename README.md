# Mari pipeline integration
For the production of our graduation film Mari was the main texturing software used. 
We needed a way to efficiently integrate it in our pipeline which was based on Mari 7.1v2

## How to intall
 Download the prism_Link.py into your Mari script folder.
 This new window will appear the next time you open Mari 
 <img width="256" height="217" alt="image" src="https://github.com/user-attachments/assets/12af1ed9-6a34-4f2b-8ae9-95d0db1e37bf" />

## Script Breakdown 

### Link Prism Asset
<img width="498" height="273" alt="image" src="https://github.com/user-attachments/assets/e9e19df0-f0d7-4e0c-b9c9-5390a93ef7d4" />

Set the Prism project Root directory for Local and global. If you don't work on a server simply ignore the option.
To set the category make sure the Asset you are trying to link to are inside a folder in your prism project browser.

#### Target Render
Leave this option Empty for now this is still in development. The goal is to directly translate to the right render format to enable lookdev auto update in main DCC.

### Export Texture
Exporting is always done locally first using the Export texture to local. The files are then copy in the corresponding prism folder on the server using the Publish texture to global option.

### Archive Mari Project
Same logic as the Texture exports. it's first done locally and can then be publish to global using the corresponding options.

### Prism Smart Export
still in development.
