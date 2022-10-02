import React, { useCallback, useState, useEffect } from "react";
import axios from "axios";
import moment from "moment";
import { useSearchParams } from "react-router-dom";
import {
  useGetNextcloudPhotosThumbnailDims,
  useNextcloudPhotosThumbnailUrls,
  useNextcloudPhotosAddToJoplin,
  useJoplinSync,
} from "../api";
import SelectedImage, { ISelectedImage } from "../components/SelectedImage";
import Gallery, { PhotoClickHandler } from "react-photo-gallery";
import { Form, Button, Alert, DatePicker, Space } from "antd";
import { useQueries, useQuery } from "react-query";
import JoplinFindNote from "../components/JoplinFindNote";

const NextcloudPhotos = () => {
  const [selectAll, setSelectAll] = useState(false);
  const [selectedIndices, setSelectedIndices] = useState<boolean[]>([]);
  const [noteId, setNoteId] = useState<string>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form] = Form.useForm();
  const [imgObjectURLs, setImgObjectURLs] = useState<any[]>([]);
  const [imgUrlsCache, setImgUrlsCache] = useState<string[]>([""]);
  const [lastSync, setLastSync] = useState<Date>();
  const [photos, setPhotos] = useState<any[]>([]);
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
  const mutationJoplinSync = useJoplinSync({
    mutation: {
      onSuccess: () => setLastSync(new Date()),
    },
  });
  const mutationNextcloudPhotosAddToJoplin = useNextcloudPhotosAddToJoplin({
    mutation: {
      onSuccess: () => mutationJoplinSync.mutate(), // run sync
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
  useEffect(() => {
    if (imgUrls) {
      setPhotos(
        imgUrls?.map((item, i) => {
          const url = `/api/nextcloud/thumbnail_img?url=${item}`;
          // const width = thumbnailDims ? thumbnailDims[i] : 512;
          // const height = thumbnailDims ? thumbnailDims[i] : 512;
          const width = 512;
          const height = 512;
          return { src: url, width: width, height: height };
        })
      );
    }
  }, [imgUrls]);

  const toggleSelectAll = () => {
    setSelectAll(!selectAll);
  };
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
    const submitPhotos = [];
    if (!imgUrls) return;
    for (let i = 0; i < imgUrls.length; i++) {
      if (selectedIndices[i] === true) {
        submitPhotos.push(imgUrls[i]);
      }
    }
    console.log(submitPhotos);
    if (submitPhotos && noteId) {
      mutationNextcloudPhotosAddToJoplin.mutate({
        noteId: noteId,
        data: submitPhotos,
      });
    }
  };

  const handleOnClick: PhotoClickHandler = (e, { index }) => {
    selectedIndices[index] = !selectedIndices[index];
    setSelectedIndices(selectedIndices);
    console.log(selectedIndices);
  };

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
        {lastSync ? <p>{`Last Joplin sync: ${lastSync}`}</p> : null}
        {mutationJoplinSync.isLoading && <p>Joplin: currently syncing...</p>}
        <JoplinFindNote
          dt={dt}
          setNoteId={setNoteId}
          lastSync={lastSync}
          setLastSync={setLastSync}
          mutationJoplinSync={mutationJoplinSync}
        />
      </Space>
      {/* <img src="/api/nextcloud/thumbnail_img?url=H1phone_sync/2022/06/22-06-24 19-07-01 4885.jpg" /> */}
      <p>Number of images found: {imgUrls.length}</p>
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
        {noteId && (
          <Button
            type="primary"
            htmlType="submit"
            loading={mutationNextcloudPhotosAddToJoplin.isLoading}
          >
            Submit
          </Button>
        )}
        {mutationNextcloudPhotosAddToJoplin.isError && (
          <Alert
            message={`Error: ${mutationNextcloudPhotosAddToJoplin.error.message}`}
            type="error"
          />
        )}
        {mutationNextcloudPhotosAddToJoplin.isSuccess && (
          <Alert
            message="Successfully added image(s) to Joplin note"
            type="success"
          />
        )}
      </Form>
    </main>
  ) : null;
};

export default NextcloudPhotos;
