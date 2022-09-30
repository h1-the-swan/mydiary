import React, { useCallback, useState, useEffect } from "react";
import axios from "axios";
import moment from "moment";
import { useSearchParams } from "react-router-dom";
import {
  useGetNextcloudPhotosThumbnailDims,
  useNextcloudPhotosThumbnailUrls,
} from "../api";
import { DatePicker, Space } from "antd";
import { useQueries, useQuery } from "react-query";

const NextcloudPhotos = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [imgObjectURLs, setImgObjectURLs] = useState<any[]>([]);
  const [imgUrlsCache, setImgUrlsCache] = useState<string[]>([""]);
  // const [imgDims, setImgDims] = useState<any[]>([]);
  if (!searchParams.get("dt")) {
    setSearchParams({ dt: "yesterday" });
  }
  const dt = searchParams.get("dt") || "yesterday";
  let dtMoment: moment.Moment;
  if (dt === "today") {
    dtMoment = moment();
  } else if (dt === "yesterday") {
    dtMoment = moment().subtract(1, "days");
  } else {
    dtMoment = moment(dt);
  }
  let { data: imgUrls, isLoading } = useNextcloudPhotosThumbnailUrls(dt, {
    query: {
      select: (d) => d.data,
    },
  });
  // const { data: thumbnailDims } = useGetNextcloudPhotosThumbnailDims(
  // const queryNextCloudPhotosThumbnailDims = useGetNextcloudPhotosThumbnailDims(
  //   {
  //     url: "",
  //   },
  //   {
  //     query: {
  //       select: (d) => d.data,
  //       enabled: false,
  //     },
  //   }
  // );
  // const thumbnailDims = useQuery(['thumbnailDims'], () => axios.get('/nextcloud/thumbnail_dims'), { placeholderData: (0,0)})
  // const { data: thumbnailDims } = useGetNextcloudPhotosThumbnailDims(
  //   {
  //     url: imgUrls && imgUrls.at(3) ? imgUrls.at(3) : "",
  //   },
  //   { query: { select: (d) => d.data } }
  // );
  const thumbnailDims = useQueries(
    imgUrlsCache.map((url) => ({
      queryKey: ["thumbnailDims", url],
      queryFn: () =>
        axios.get("/nextcloud/thumbnail_dims", { params: { url: url } }),
    }))
  );
  useEffect(() => {
    if (imgUrls) {
      setImgUrlsCache(imgUrls);
    }
    const imgs = imgUrls?.map((url) => {
      // console.log(url);
      // .then((response) => response.blob())
      // .then((imgBlob) => {
      //   const imgObjectURL = URL.createObjectURL(imgBlob);
      //   console.log(imgObjectURL);
      //   console.log(imgBlob);
      //   const image = document.createElement("img");
      //   image.src = imgObjectURL;
      //   const container = document.getElementById("container");
      //   if (container) {
      //     container.append(image);
      //   }
      // });
    });
  }, [imgUrls]);
  useEffect(() => {
    if (!thumbnailDims.filter((result) => result.isLoading).length) {
      const disp = thumbnailDims.map((result) =>
        result.data ? result.data.data : undefined
      );
      console.log(disp);
    }
  }, [thumbnailDims]);
  return isLoading ? (
    <span>Loading...</span>
  ) : imgUrls ? (
    <main id="container">
      <Space direction="vertical">
        <DatePicker
          defaultValue={dtMoment}
          onChange={(date: any, dateString: string) => {
            setSearchParams({ dt: dateString });
          }}
        />
      </Space>
      {/* <img src="/api/nextcloud/thumbnail_img?url=H1phone_sync/2022/06/22-06-24 19-07-01 4885.jpg" /> */}
      {imgUrls.map((url) => (
        <img src={`/api/nextcloud/thumbnail_img?url=${url}`} alt="" />
      ))}
    </main>
  ) : null;
};

export default NextcloudPhotos;
