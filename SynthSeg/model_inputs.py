# python imports
import numpy as np
import numpy.random as npr

# third-party imports
from ext.lab2im import utils


def build_model_inputs(path_label_maps,
                       n_labels,
                       batch_size=1,
                       n_channels=1,
                       prior_distributions='uniform',
                       prior_means=None,
                       prior_stds=None,
                       use_specific_stats_for_channel=False,
                       generation_classes=None,
                       apply_linear_trans=True,
                       scaling_bounds=None,
                       rotation_bounds=None,
                       shearing_bounds=None,
                       apply_nonlin_trans=True,
                       nonlin_shape_factor=.0625,
                       nonlin_std_dev=3,
                       apply_bias_field=True,
                       bias_field_shape=None,
                       bias_shape_factor=.025,
                       bias_field_std_dev=.3,
                       background_paths=None):
    """
    This function builds a generator to be fed to the lab2im model. It enables to generate all the required inputs,
    according to the operations performed in the model.
    :param path_label_maps: list of the paths of the input label maps.
    :param n_labels: number of labels in the input label maps.
    :param batch_size: (optional) numbers of images to generate per mini-batch. Default is 1.
    :param n_channels: (optional) number of channels to be synthetised. Default is 1.
    :param prior_distributions: (optional) type of distribution from which we sample the GMM parameters.
    Can either be 'uniform', or 'normal'. Default is 'uniform'.
    :param prior_means: (optional) hyperparameters controlling the prior distributions of the GMM means. Because
    these prior distributions are uniform or normal, they require by 2 hyperparameters. Thus prior_means can be:
    1) a sequence of length 2, directly defining the two hyperparameters: [min, max] if prior_distributions is
    uniform, [mean, std] if the distribution is normal. The GMM means of are independently sampled at each
    mini_batch from the same distribution.
    2) an array of shape (2, n_labels). The mean of the Gaussian distribution associated to label k is sampled at
    each mini_batch from U(prior_means[0,k], prior_means[1,k]) if prior_distributions is uniform, and from
    N(prior_means[0,k], prior_means[1,k]) if prior_distributions is normal.
    3) an array of shape (2*n_mod, n_labels), where each block of two rows is associated to hyperparameters derived
    from different modalities. In this case, if use_specific_stats_for_channel is False, we first randomly select a
    modality from the n_mod possibilities, and we sample the GMM means like in 2).
    If use_specific_stats_for_channel is True, each block of two rows correspond to a different channel
    (n_mod=n_channels), thus we select the corresponding block to each channel rather than randomly drawing it.
    4) the path to such a numpy array.
    Default is None, which corresponds to prior_means = [25, 225].
    :param prior_stds: (optional) same as prior_means but for the standard deviations of the GMM.
    Default is None, which corresponds to prior_stds = [5, 25].
    :param use_specific_stats_for_channel: (optional) whether the i-th block of two rows in the prior arrays must be
    only used to generate the i-th channel. If True, n_mod should be equal to n_channels. Default is False.
    :param generation_classes: (optional) Indices regrouping generation labels into classes when sampling the GMM.
    Intensities of corresponding to regouped labels will thus be sampled from the same distribution. Must have the
    same length as generation_labels. Can be a sequence, a 1d numpy array, or the path to a 1d numpy array.
    Default is all labels have different classes.
    :param apply_linear_trans: (optional) whether to apply affine deformation. Default is True.
    :param scaling_bounds: (optional) if apply_linear_trans is True, the scaling factor for each dimension is
    sampled from a uniform distribution of predefined bounds. Can either be:
    1) a number, in which case the scaling factor is independently sampled from the uniform distribution of bounds
    (1-scaling_bounds, 1+scaling_bounds) for each dimension.
    2) a sequence, in which case the scaling factor is sampled from the uniform distribution of bounds
    (1-scaling_bounds[i], 1+scaling_bounds[i]) for the i-th dimension.
    3) a numpy array of shape (2, n_dims), in which case the scaling factor is sampled from the uniform distribution
     of bounds (scaling_bounds[0, i], scaling_bounds[1, i]) for the i-th dimension.
    If None (default), scaling_range = 0.15
    :param rotation_bounds: (optional) same as scaling bounds but for the rotation angle, except that for cases 1
    and 2, the bounds are centred on 0 rather than 1, i.e. (0+rotation_bounds[i], 0-rotation_bounds[i]).
    If None (default), rotation_bounds = 15.
    :param shearing_bounds: (optional) same as scaling bounds. If None (default), shearing_bounds = 0.01.
    :param apply_nonlin_trans: (optional) whether to apply non linear elastic deformation.
    If true, a diffeomorphic deformation field is obtained by first sampling a small tensor from the normal
    distribution, resizing it to image size, and integrationg it. Default is True.
    :param nonlin_shape_factor: (optional) If apply_nonlin_trans is True, ratio between the size of the input label
    maps and the size of the sampled tensor for synthesising the deformation field.
    :param nonlin_std_dev: (optional) If apply_nonlin_trans is True, standard deviation of the normal distribution
    from which we sample the first tensor for synthesising the deformation field.
    :param apply_bias_field: (optional) whether to apply a bias field to the final image. Default is True.
    If True, the bias field is obtained by sampling a first tensor from normal distribution, resizing it to image
    size, and rescaling the values to positive number by taking the voxel-wise exponential. Default is True.
    :param bias_field_shape: (optional) Shape of the final bias field that will be applied to synthesised images.
    Must be provided if apply_bias_field is True.
    :param bias_shape_factor: (optional) If apply_bias_field is True, ratio between the size of the input
    label maps and the size of the sampled tensor for synthesising the bias field.
    :param bias_field_std_dev: (optional) If apply_nonlin_trans is True, standard deviation of the normal
    distribution from which we sample the first tensor for synthesising the deformation field.
    :param background_paths: (optional) list of paths of label maps to replace the soft brain tissues (label 258) with.
    """

    # get label info
    labels_shape, _, n_dims, _, _, _ = utils.get_volume_info(path_label_maps[0])

    # Generate!
    while True:

        # randomly pick as many images as batch_size
        label_map_indices = npr.randint(len(path_label_maps), size=batch_size)

        # initialise input tensors
        y_all = []
        means_all = []
        std_devs_all = []
        aff_all = []
        nonlinear_field_all = []
        bias_field_all = []

        for label_map_idx in label_map_indices:

            # add labels to inputs
            y = utils.load_volume(path_label_maps[label_map_idx], dtype='int')
            if background_paths is not None:
                idx_258 = np.where(y == 258)
                if np.any(idx_258):
                    background = utils.load_volume(background_paths[npr.randint(len(background_paths))], dtype='int')
                    background_shape = background.shape
                    if np.all(np.array(background_shape) == background_shape[0]):  # flip if same dimensions
                        background = np.flip(background, tuple([i for i in range(3) if np.random.normal() > 0]))
                    assert background.shape == y.shape, 'background patches should have same shape than training ' \
                                                        'labels. Had {0} and {1}'.format(background.shape, y.shape)
                    y[idx_258] = background[idx_258]
            y_all.append(utils.add_axis(y, axis=-2))

            # add means and standard deviations to inputs
            means = np.empty((n_labels, 0))
            std_devs = np.empty((n_labels, 0))
            for channel in range(n_channels):

                # retrieve channel specific stats if necessary
                if isinstance(prior_means, np.ndarray):
                    if prior_means.shape[0] > 2 & use_specific_stats_for_channel:
                        if prior_means.shape[0] / 2 != n_channels:
                            raise ValueError("the number of blocks in prior_means does not match n_channels. This "
                                             "message is printed because use_specific_stats_for_channel is True.")
                        tmp_prior_means = prior_means[2 * channel:2 * channel + 2, :]
                    else:
                        tmp_prior_means = prior_means
                else:
                    tmp_prior_means = prior_means
                if isinstance(prior_stds, np.ndarray):
                    if prior_stds.shape[0] > 2 & use_specific_stats_for_channel:
                        if prior_stds.shape[0] / 2 != n_channels:
                            raise ValueError("the number of blocks in prior_stds does not match n_channels. This "
                                             "message is printed because use_specific_stats_for_channel is True.")
                        tmp_prior_stds = prior_stds[2 * channel:2 * channel + 2, :]
                    else:
                        tmp_prior_stds = prior_stds
                else:
                    tmp_prior_stds = prior_stds

                # draw means and std devs from priors
                tmp_means = utils.add_axis(utils.draw_value_from_distribution(
                    tmp_prior_means, n_labels, prior_distributions, 125., 100.), -1)
                tmp_stds = utils.add_axis(utils.draw_value_from_distribution(
                    tmp_prior_stds, n_labels, prior_distributions, 15., 10.), -1)
                # share stats between labels of the same class
                if generation_classes is not None:
                    unique_classes, unique_indices = np.unique(generation_classes, return_index=True)
                    unique_tmp_means = tmp_means[unique_indices]
                    unique_tmp_stds = tmp_stds[unique_indices]
                    for idx_class, tmp_class in enumerate(unique_classes):
                        tmp_means[generation_classes == tmp_class] = unique_tmp_means[idx_class]
                        tmp_stds[generation_classes == tmp_class] = unique_tmp_stds[idx_class]
                means = np.concatenate([means, tmp_means], axis=1)
                std_devs = np.concatenate([std_devs, tmp_stds], axis=1)
            means_all.append(utils.add_axis(means))
            std_devs_all.append(utils.add_axis(std_devs))

            # add inputs according to augmentation specification
            if apply_linear_trans:
                # get affine transformation: rotate, scale, shear (translation done during random cropping)
                scaling = utils.draw_value_from_distribution(scaling_bounds, size=n_dims, centre=1, default_range=.15)
                if n_dims == 2:
                    rotation = utils.draw_value_from_distribution(rotation_bounds, default_range=15.0)
                else:
                    rotation = utils.draw_value_from_distribution(rotation_bounds, size=n_dims, default_range=15.0)
                shearing = utils.draw_value_from_distribution(shearing_bounds, size=n_dims**2-n_dims, default_range=.01)
                aff = utils.create_affine_transformation_matrix(n_dims, scaling, rotation, shearing)
                aff_all.append(utils.add_axis(aff))

            if apply_nonlin_trans:
                deform_shape = utils.get_resample_shape(labels_shape[:n_dims], nonlin_shape_factor, len(labels_shape))
                nonlinear_field = npr.normal(loc=0, scale=nonlin_std_dev * npr.rand(), size=deform_shape)
                nonlinear_field_all.append(utils.add_axis(nonlinear_field))

            if apply_bias_field:
                bias_shape = utils.get_resample_shape(bias_field_shape[:n_dims], bias_shape_factor, n_channels=1)
                bias_field = npr.normal(loc=0, scale=bias_field_std_dev * npr.rand(), size=bias_shape)
                bias_field_all.append(utils.add_axis(bias_field))

        # build list of inputs to augmentation model
        inputs_vals = [y_all, means_all, std_devs_all]
        if apply_linear_trans:
            inputs_vals.append(aff_all)
        if apply_nonlin_trans:
            inputs_vals.append(nonlinear_field_all)
        if apply_bias_field:
            inputs_vals.append(bias_field_all)

        # put images and labels (concatenated if batch_size>1) into a tuple of 2 elements: (cat_images, cat_labels)
        if batch_size > 1:
            inputs_vals = [np.concatenate(item, 0) for item in inputs_vals]
        else:
            inputs_vals = [item[0] for item in inputs_vals]

        yield inputs_vals


def means_stds_fs_labels_with_relations(means_range, std_devs_range, min_diff=15, head=True):

    # draw gm wm and csf means
    gm_wm_csf_means = np.zeros(3)
    while (abs(gm_wm_csf_means[1] - gm_wm_csf_means[0]) < min_diff) | \
          (abs(gm_wm_csf_means[1] - gm_wm_csf_means[2]) < min_diff) | \
          (abs(gm_wm_csf_means[0] - gm_wm_csf_means[2]) < min_diff):
        gm_wm_csf_means = utils.add_axis(utils.draw_value_from_distribution(means_range, 3, 'uniform', 125., 100.), -1)

    # apply relations
    wm = gm_wm_csf_means[0]
    gm = gm_wm_csf_means[1]
    csf = gm_wm_csf_means[2]
    csf_like = csf * npr.uniform(low=0.95, high=1.05)
    alpha_thalamus = npr.uniform(low=0.4, high=0.9)
    thalamus = alpha_thalamus*gm + (1-alpha_thalamus)*wm
    cerebellum_wm = wm * npr.uniform(low=0.7, high=1.3)
    cerebellum_gm = gm * npr.uniform(low=0.7, high=1.3)
    caudate = gm * npr.uniform(low=0.9, high=1.1)
    putamen = gm * npr.uniform(low=0.9, high=1.1)
    hippocampus = gm * npr.uniform(low=0.9, high=1.1)
    amygdala = gm * npr.uniform(low=0.9, high=1.1)
    accumbens = caudate * npr.uniform(low=0.9, high=1.1)
    pallidum = wm * npr.uniform(low=0.8, high=1.2)
    brainstem = wm * npr.uniform(low=0.8, high=1.2)
    alpha_ventralDC = npr.uniform(low=0.1, high=0.6)
    ventralDC = alpha_ventralDC*gm + (1-alpha_ventralDC)*wm
    alpha_choroid = npr.uniform(low=0.0, high=1.0)
    choroid = alpha_choroid*csf + (1-alpha_choroid)*wm

    # regroup structures
    neutral_means = [np.zeros(1), csf_like, csf_like, brainstem, csf]
    sided_means = [wm, gm, csf_like, csf_like, cerebellum_wm, cerebellum_gm, thalamus, caudate, putamen, pallidum,
                   hippocampus, amygdala, accumbens, ventralDC, choroid]

    # draw std deviations
    std = utils.add_axis(utils.draw_value_from_distribution(std_devs_range, 17, 'uniform', 15., 10.), -1)
    neutral_stds = [np.zeros(1), std[1], std[1], std[2], std[3]]
    sided_stds = [std[4], std[5], std[1], std[1], std[6], std[7], std[8], std[9], std[10], std[11], std[12], std[13],
                  std[14], std[15], std[16]]

    # add means and variances for extra head labels if necessary
    if head:
        # means
        extra_means = utils.add_axis(utils.draw_value_from_distribution(means_range, 2, 'uniform', 125., 100.), -1)
        skull = extra_means[0]
        soft_non_brain = extra_means[1]
        eye = csf * npr.uniform(low=0.95, high=1.05)
        optic_chiasm = wm * npr.uniform(low=0.8, high=1.2)
        vessel = csf * npr.uniform(low=0.7, high=1.3)
        neutral_means += [csf_like, optic_chiasm, skull, soft_non_brain, eye]
        sided_means.insert(-1, vessel)
        # std dev
        extra_std = utils.add_axis(utils.draw_value_from_distribution(std_devs_range, 4, 'uniform', 15., 10.), -1)
        neutral_stds += [std[1], extra_std[0], extra_std[1], extra_std[2], std[1]]
        sided_stds.insert(-1, extra_std[3])

    means = np.concatenate([np.array(neutral_means), np.array(sided_means), np.array(sided_means)])
    stds = np.concatenate([np.array(neutral_stds), np.array(sided_stds), np.array(sided_stds)])

    return means, stds
