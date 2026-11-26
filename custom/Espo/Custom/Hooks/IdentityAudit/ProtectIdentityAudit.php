<?php

namespace Espo\Custom\Hooks\IdentityAudit;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Custom\Classes\Identity\IdentityPolicy;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * CRM-IDINT-001 (3.2): identity audit records are written only by the server
 * (IdentityAuditor sets a save option no API request can carry) and are never
 * edited or deleted through the application. There is no exemption for
 * administrators: they bypass role ACL, not hooks.
 *
 * @implements BeforeSave<Entity>
 * @implements BeforeRemove<Entity>
 */
class ProtectIdentityAudit implements BeforeSave, BeforeRemove
{
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if (!$entity->isNew()) {
            throw new Forbidden('Identity audit records cannot be changed.');
        }

        if (IdentityPolicy::option($options, IdentityPolicy::AUDIT_WRITE_OPTION) !== true) {
            throw new Forbidden('Identity audit records are written by ERm only.');
        }
    }

    public function beforeRemove(Entity $entity, RemoveOptions $options): void
    {
        throw new Forbidden('Identity audit records cannot be deleted.');
    }
}
