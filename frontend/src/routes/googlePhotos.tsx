import React from "react";
import { useGooglePhotosThumbnailUrls } from "../api";

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
  return isLoading ? (
    <span>Loading...</span>
  ) : imgUrls ? (
    <main>
      {imgUrls.map((url) => (
        <img src={url} alt="googlephoto thumbnail" />
      ))}
    </main>
  ) : null;
};

export default GooglePhotos;
