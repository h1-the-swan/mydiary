import React, { useCallback, useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Form, Button } from "antd";
import { useGooglePhotosThumbnailUrls } from "../api";
import Gallery, { PhotoClickHandler } from "react-photo-gallery";
import SelectedImage, { ISelectedImage } from "../components/SelectedImage";
import { RenderImageProps, GalleryI } from "react-photo-gallery";

const GooglePhotos = () => {
  const [selectAll, setSelectAll] = useState(false);
  const [selectedIndices, setSelectedIndices] = useState<boolean[]>([]);
  const [form] = Form.useForm();
  const params = useParams();
  const { data: imgUrls, isLoading } = useGooglePhotosThumbnailUrls(
    params.dt || "2022-03-01",
    {
      query: {
        select: (d) => d.data,
      },
    }
  );

  const toggleSelectAll = () => {
    setSelectAll(!selectAll);
  };
  const photos = imgUrls?.map((item) => {
    const { url, width, height } = item;
    return { src: url, width: width, height: height };
  });

  useEffect(() => {
    if (imgUrls) {
      setSelectedIndices(new Array(imgUrls.length).fill(false));
      setSelectAll(false);
    }
  }, [imgUrls]);

  const imageRenderer = useCallback(
    (props: ISelectedImage) => {
      const { index, photo, left, top, direction, onClick } = props;
      photo.selected = selectAll ? true : false;
      return (
        <SelectedImage
          key={photo.key}
          margin={"2px"}
          index={index}
          photo={photo}
          left={left}
          top={top}
          direction={direction}
          onClick={onClick}
        />
      );
    },
    [selectAll]
  );

  const onFinish = (values: any) => {
    console.log(values);
  };

  const handleOnClick: PhotoClickHandler = (e, { index }) => {
    selectedIndices[index] = !selectedIndices[index];
    setSelectedIndices(selectedIndices);
    console.log(selectedIndices);
  };

  return isLoading ? (
    <span>Loading...</span>
  ) : photos ? (
    <main>
      <Form form={form} onFinish={onFinish}>
        <Button onClick={toggleSelectAll}>toggle select all</Button>
        <Form.Item name="gallery">
          <div>
            <Gallery
              photos={photos}
              onClick={handleOnClick}
              renderImage={imageRenderer}
            />
          </div>
        </Form.Item>
        <Button type="primary" htmlType="submit">
          Submit
        </Button>
      </Form>
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
