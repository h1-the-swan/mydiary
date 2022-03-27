// https://codesandbox.io/s/o7o241q09?file=/SelectedImage.js:0-2199

import React, { useState, useEffect } from "react";
import { Image, ImageProps } from "antd";
import { RenderImageProps, PhotoProps } from "react-photo-gallery";
import { isElement } from "react-dom/test-utils";

const Checkmark = (props: { selected: boolean }) => (
  <div
    style={
      props.selected
        ? { left: "4px", top: "4px", position: "absolute", zIndex: "1" }
        : { display: "none" }
    }
  >
    <svg
      style={{ fill: "white", position: "absolute" }}
      width="24px"
      height="24px"
    >
      <circle cx="12.5" cy="12.2" r="8.292" />
    </svg>
    <svg
      style={{ fill: "#06befa", position: "absolute" }}
      width="24px"
      height="24px"
    >
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
    </svg>
  </div>
);

const imgStyle = {
  transition: "transform .135s cubic-bezier(0.0,0.0,0.2,1),opacity linear .15s",
};
const selectedImgStyle = {
  transform: "translateZ(0px) scale3d(0.9, 0.9, 1)",
  transition: "transform .135s cubic-bezier(0.0,0.0,0.2,1),opacity linear .15s",
};
const cont: any = {
  backgroundColor: "#eee",
  cursor: "pointer",
  overflow: "hidden",
  position: "relative",
};

export interface IPhoto extends PhotoProps {
  // sizes?: string;
  // srcSet?: string;
  selected?: boolean;
}

export interface ISelectedImage extends RenderImageProps {
  photo: IPhoto;
}

// const SelectedImage = (props: RenderImageProps<{selected: boolean}>) => {
//   const { index, photo, margin, direction, top, left, onClick, selected} = props;
const SelectedImage = (props: ISelectedImage) => {
  const {  index, photo, left, top, direction, onClick, margin } = props;
  const { selected } = photo;

  const [isSelected, setIsSelected] = useState(selected);
  //calculate x,y scale
  const sx = (100 - (30 / photo.width) * 100) / 100;
  const sy = (100 - (30 / photo.height) * 100) / 100;
  selectedImgStyle.transform = `translateZ(0px) scale3d(${sx}, ${sy}, 1)`;

  if (direction === "column") {
    cont.position = "absolute";
    cont.left = left;
    cont.top = top;
  }

  const handleOnClick = (e: any) => {
    if (onClick) onClick(e, { index });
    setIsSelected(!isSelected);
  };

  useEffect(() => {
    setIsSelected(selected);
  }, [selected]);

  let { sizes, srcSet, ...photoProps } = photo;
  sizes = Array.isArray(sizes) ? sizes.join(",") : sizes;
  srcSet = Array.isArray(srcSet) ? srcSet.join(",") : srcSet
  // delete photo.sizes;
  // delete photo.srcSet;

  
  return (
    <div
      style={{ margin, height: photo.height, width: photo.width, ...cont }}
      className={!isSelected ? "not-selected" : ""}
      onClick={handleOnClick}
    >
      <Checkmark selected={isSelected ? true : false} />
      <Image
        preview={false}
        // alt={photo.title}kk
        style={
          isSelected ? { ...imgStyle, ...selectedImgStyle } : { ...imgStyle }
        }
        sizes={sizes}
        srcSet={srcSet}
        {...photoProps}
      />
      <style>{`.not-selected:hover{outline:2px solid #06befa}`}</style>
    </div>
  );
};

export default SelectedImage;
