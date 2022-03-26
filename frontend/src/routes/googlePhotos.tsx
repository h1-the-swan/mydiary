import React from "react";
import { useGooglePhotosThumbnailUrls } from "../api";
import Gallery from "react-photo-gallery";

const GooglePhotos = () => {
  const { data: imgUrls, isLoading } = useGooglePhotosThumbnailUrls(
    "2022-03-01",
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
  // return <main>{imgUrls.map}</main>;
  const photos = imgUrls?.map((item) => {
    const { url, width, height } = item;
    return { src: url, width: width, height: height };
  });
  return isLoading ? (
    <span>Loading...</span>
  ) : photos ? (
    <main>
      <Gallery photos={photos} />
    </main>
  ) : null;
};

export default GooglePhotos;

// import React, { useState, useCallback } from "react";
// import { render } from "react-dom";
// import Gallery from "react-photo-gallery";
// import SelectedImage from "./SelectedImage";
// import { photos } from "./photos";

// function App() {
//   const [selectAll, setSelectAll] = useState(false);

//   const toggleSelectAll = () => {
//     setSelectAll(!selectAll);
//   };

//   const imageRenderer = useCallback(
//     ({ index, left, top, key, photo }) => (
//       <SelectedImage
//         selected={selectAll ? true : false}
//         key={key}
//         margin={"2px"}
//         index={index}
//         photo={photo}
//         left={left}
//         top={top}
//       />
//     ),
//     [selectAll]
//   );

//   return (
//     <div>
//       <p>
//         <button onClick={toggleSelectAll}>toggle select all</button>
//       </p>
//       <Gallery photos={photos} renderImage={imageRenderer} />
//     </div>
//   );
// }

// render(<App />, document.getElementById("app"));
